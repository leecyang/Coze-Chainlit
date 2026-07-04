import matchers from '@testing-library/jest-dom/matchers';
import { expect } from 'vitest';

expect.extend(matchers);

Object.defineProperty(window, 'cl_shadowRootElement', {
  configurable: true,
  value: document.body
});
