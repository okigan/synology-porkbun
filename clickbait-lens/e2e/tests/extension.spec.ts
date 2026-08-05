import { expect, test } from "./fixtures";

test.describe("Clickbait Lens in a real browser", () => {
  test("flags an overstated headline and highlights the sentence that undercuts it", async ({
    context,
  }) => {
    const page = await context.newPage();
    await page.goto("/overstated.html");

    const badge = page.getByTestId("cbl-badge");
    await expect(badge).toBeVisible();

    const score = Number(await page.getByTestId("cbl-score").innerText());
    expect(score).toBeGreaterThan(30);

    await badge.click();
    await expect(page.getByTestId("cbl-panel")).toBeVisible();

    // The headline states as fact what the body hedges and attributes.
    const signals = page.getByTestId("cbl-signal");
    await expect(signals.first()).toBeVisible();
    const ids = await signals.evaluateAll((nodes) =>
      nodes.map((node) => (node as HTMLElement).dataset.signalId),
    );
    expect(ids).toEqual(
      expect.arrayContaining([
        expect.stringMatching(/assertive_headline_hedged_body|attribution_stripped/),
      ]),
    );

    // Body sentences the headline overstates are marked up in the page itself.
    const highlights = page.locator("mark.clickbait-lens-highlight");
    await expect(highlights.first()).toBeVisible();
    expect(await highlights.count()).toBeGreaterThan(0);

    // Clicking the quoted evidence jumps to that sentence.
    await page.getByTestId("cbl-evidence").first().click();
    await expect(page.locator('mark[data-cbl-active="true"]')).toHaveCount(1);
  });

  test("a straight news headline scores low and highlights nothing", async ({ context }) => {
    const page = await context.newPage();
    await page.goto("/clean.html");

    await expect(page.getByTestId("cbl-badge")).toBeVisible();
    const score = Number(await page.getByTestId("cbl-score").innerText());
    expect(score).toBeLessThan(25);
    await expect(page.locator("mark.clickbait-lens-highlight")).toHaveCount(0);
  });

  test("resolves the byline to an author and shows their track record", async ({ context }) => {
    const page = await context.newPage();
    await page.goto("/clean.html");

    // Seeded demo data gives Helena Marsh a real record to display.
    await expect(page.getByTestId("cbl-badge-subtitle")).toContainText("Helena Marsh");

    await page.getByTestId("cbl-badge").click();
    await page.getByTestId("cbl-tab-authors").click();

    const author = page.getByTestId("cbl-author").first();
    await expect(author).toContainText("Helena Marsh");
    await expect(author).toContainText("economist.com");

    const trust = Number(await page.getByTestId("cbl-trust-index").first().innerText());
    expect(trust).toBeGreaterThan(60);
  });

  test("verifies a prediction against live search and records the verdict", async ({
    context,
  }) => {
    const page = await context.newPage();
    await page.goto("/predictions.html");

    await page.getByTestId("cbl-badge").click();
    await page.getByTestId("cbl-tab-claims").click();

    const claim = page
      .getByTestId("cbl-claim")
      .filter({ hasText: "never return to a physical office" })
      .first();
    await expect(claim).toBeVisible();

    await claim.getByTestId("cbl-verify").click();

    const verification = claim.getByTestId("cbl-verification");
    await expect(verification).toBeVisible();
    // The fixture corpus refutes this prediction.
    await expect(verification).toContainText(/did not happen|mostly false/);
    await expect(verification.locator("li").first()).toContainText("refutes");

    await claim.getByTestId("cbl-accept").click();
    await expect(claim.getByTestId("cbl-claim-resolution")).toContainText(
      /did not happen|mostly false/,
    );
  });

  test("a resolved prediction moves the author's trust index", async ({ context }) => {
    const page = await context.newPage();
    await page.goto("/predictions.html");
    await page.getByTestId("cbl-badge").click();

    await page.getByTestId("cbl-tab-authors").click();
    const before = Number(await page.getByTestId("cbl-trust-index").first().innerText());

    await page.getByTestId("cbl-tab-claims").click();
    const claim = page
      .getByTestId("cbl-claim")
      .filter({ hasText: "vacancy rates will exceed 40 percent" })
      .first();
    await claim.getByTestId("cbl-mark-false").click();
    await expect(claim.getByTestId("cbl-claim-resolution")).toContainText("did not happen");

    await page.getByTestId("cbl-refresh").click();
    await page.getByTestId("cbl-tab-authors").click();
    await expect
      .poll(async () => Number(await page.getByTestId("cbl-trust-index").first().innerText()))
      .toBeLessThan(before);
  });

  test("stays out of the way on pages that are not articles", async ({ context }) => {
    const page = await context.newPage();
    await page.goto("/not-an-article.html");
    await page.waitForTimeout(1200);
    await expect(page.getByTestId("cbl-badge")).toHaveCount(0);
    await expect(page.getByTestId("cbl-panel")).toHaveCount(0);
  });

  test("popup reports backend health and the active tab's analysis", async ({
    context,
    extensionId,
  }) => {
    const page = await context.newPage();
    await page.goto("/overstated.html");
    await expect(page.getByTestId("cbl-badge")).toBeVisible();
    await page.bringToFront();

    const popup = await context.newPage();
    await popup.goto(`chrome-extension://${extensionId}/popup.html`);

    await expect(popup.getByTestId("popup-health")).toHaveText("backend online");
    await expect(popup.getByTestId("popup-api-base")).toHaveValue("http://127.0.0.1:8901");
  });

  test("surfaces a clear error when the backend is unreachable", async ({ context }) => {
    const worker = context.serviceWorkers()[0];
    await worker.evaluate(async () => {
      await chrome.storage.local.set({ apiBase: "http://127.0.0.1:9" });
    });

    const page = await context.newPage();
    await page.goto("/overstated.html");
    await expect(page.getByTestId("cbl-error")).toContainText("Cannot reach");
  });
});
