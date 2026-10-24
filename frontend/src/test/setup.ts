import "@testing-library/jest-dom/vitest";

// jsdom does not implement ResizeObserver; React Flow and other layout libs
// depend on it. A no-op stub keeps component tests focused on behaviour.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (!("ResizeObserver" in globalThis)) {
  (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub;
}
