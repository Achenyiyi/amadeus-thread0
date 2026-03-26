import { loadMockSession, type MockSession } from "../data/mockBackend";

export interface BackendClient {
  loadSessionSnapshot(): Promise<MockSession>;
}

class MockBackendClient implements BackendClient {
  async loadSessionSnapshot(): Promise<MockSession> {
    return loadMockSession();
  }
}

export function createBackendClient(): BackendClient {
  return new MockBackendClient();
}
