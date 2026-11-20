# Playwright runner for `make test`. Browsers come with the image; versions must match.
FROM mcr.microsoft.com/playwright:v1.65.1-noble
WORKDIR /e2e
RUN npm init -y >/dev/null && npm install --no-audit --no-fund @playwright/test@1.65.1
COPY playwright.config.ts ./
COPY e2e ./e2e
CMD ["npx", "playwright", "test"]
