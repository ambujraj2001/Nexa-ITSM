import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement layout APIs used for auto-scrolling.
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => undefined;
