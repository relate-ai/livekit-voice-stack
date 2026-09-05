import { ConnectionState, Room, RoomEvent, Track } from 'livekit-client';

type SessionResponse = {
  server_url: string;
  token: string;
  room_name: string;
};

const startButton = document.querySelector<HTMLButtonElement>('#start')!;
const endButton = document.querySelector<HTMLButtonElement>('#end')!;
const statusText = document.querySelector<HTMLElement>('#status')!;
const detailText = document.querySelector<HTMLElement>('#detail')!;
const errorText = document.querySelector<HTMLElement>('#error')!;
const orb = document.querySelector<HTMLElement>('.orb')!;
const audioHost = document.querySelector<HTMLElement>('#audio')!;

let room: Room | null = null;
let userWasSpeaking = false;

class UserFacingError extends Error {}

function setState(state: 'ready' | 'connecting' | 'listening' | 'thinking' | 'speaking' | 'error') {
  statusText.textContent = state[0].toUpperCase() + state.slice(1);
  orb.dataset.state = state;
  detailText.textContent = {
    ready: 'One click starts a continuous hands-free conversation.',
    connecting: 'Creating a secure room and connecting your microphone.',
    listening: 'Speak naturally. Pause when your turn is complete.',
    thinking: 'Your assistant is preparing a response.',
    speaking: 'You can interrupt by speaking at any time.',
    error: 'The conversation could not continue.',
  }[state];
}

function showError(message: string) {
  errorText.textContent = message;
  setState('error');
}

async function endConversation() {
  await room?.disconnect(true);
  room = null;
  audioHost.replaceChildren();
  startButton.disabled = false;
  endButton.disabled = true;
  errorText.textContent = '';
  setState('ready');
}

async function startConversation() {
  startButton.disabled = true;
  errorText.textContent = '';
  setState('connecting');

  try {
    room = new Room({ adaptiveStream: true, dynacast: true });
    await room.startAudio();

    room.on(RoomEvent.ConnectionStateChanged, (state) => {
      if (state === ConnectionState.Reconnecting) setState('connecting');
      if (state === ConnectionState.Disconnected && endButton.disabled === false) {
        showError('Connection ended. Select Start Conversation to reconnect.');
      }
    });
    room.on(RoomEvent.TrackSubscribed, (track) => {
      if (track.kind === Track.Kind.Audio) {
        const element = track.attach();
        element.autoplay = true;
        audioHost.append(element);
      }
    });
    room.on(RoomEvent.TrackUnsubscribed, (track) => track.detach().forEach((node) => node.remove()));
    room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
      const localSpeaking = speakers.some((participant) => participant.identity === room?.localParticipant.identity);
      const remoteSpeaking = speakers.some((participant) => participant.identity !== room?.localParticipant.identity);
      if (localSpeaking) {
        userWasSpeaking = true;
        setState('listening');
      } else if (remoteSpeaking) {
        userWasSpeaking = false;
        setState('speaking');
      } else if (userWasSpeaking) {
        userWasSpeaking = false;
        setState('thinking');
      }
    });
    room.on(RoomEvent.AudioPlaybackStatusChanged, () => {
      if (room && !room.canPlaybackAudio) {
        showError('Audio playback was blocked. Select Start Conversation again to enable it.');
      }
    });

    const response = await fetch('/api/session', {
      method: 'POST',
      credentials: 'same-origin',
    });
    if (!response.ok) {
      throw new UserFacingError(
        response.status === 429
          ? 'Session limit reached. Try again later.'
          : 'Unable to create a secure session.',
      );
    }
    const session = (await response.json()) as SessionResponse;

    await room.connect(session.server_url, session.token);
    await room.localParticipant.setMicrophoneEnabled(true);
    endButton.disabled = false;
    setState('listening');
  } catch (error) {
    await room?.disconnect(true);
    room = null;
    startButton.disabled = false;
    endButton.disabled = true;
    if (error instanceof UserFacingError) {
      showError(error.message);
    } else if (error instanceof DOMException && error.name === 'NotAllowedError') {
      showError('Microphone permission is required to start a conversation.');
    } else {
      showError('The conversation could not connect. Try again.');
    }
  }
}

startButton.addEventListener('click', startConversation);
endButton.addEventListener('click', endConversation);
window.addEventListener('beforeunload', () => room?.disconnect(true));
