export {};

declare global {
  interface Window {
    amadeusDesktop?: {
      isElectron: boolean;
      backendBase?: string;
      getBackendBase(): Promise<string>;
      getCapabilities(): Promise<unknown>;
      startBackend(): Promise<unknown>;
      stopBackend(): Promise<unknown>;
      listDevices(): Promise<unknown>;
      startCall(): Promise<unknown>;
      stopCall(): Promise<unknown>;
      setMicMuted(muted: boolean): Promise<unknown>;
      setCameraEnabled(enabled: boolean): Promise<unknown>;
      submitAudioChunk(payload: unknown): Promise<unknown>;
      submitVideoFrame(payload: unknown): Promise<unknown>;
      submitArtifact(payload: unknown): Promise<unknown>;
    };
  }
}
