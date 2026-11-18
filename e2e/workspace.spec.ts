import { expect, test } from "@playwright/test";
import type { ClaimDetail, Instructions } from "../dashboard/src/types";

test("full evidence and read-only instructions match the backend and retain selection", async ({
  page,
  request,
}) => {
  const detail = (await (
    await request.get("/api/claims/CLM-T420")
  ).json()) as ClaimDetail;
  const instructions = (await (
    await request.get("/api/agent/instructions")
  ).json()) as Instructions;
  await page.goto("/");
  await expect(page.getByText("6 claims", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Open claim CLM-T420", exact: true })
    .click();
  const region = page.getByRole("region", { name: "Claim details" });
  await expect(region).toContainText(detail.claim.story);
  for (const document of detail.claim.documents) {
    await region.locator("summary").filter({ hasText: document.name }).click();
    await expect(
      region.getByText(document.content, { exact: true }),
    ).toBeVisible();
  }
  await page
    .getByRole("button", { name: "Agent instructions", exact: true })
    .click();
  await expect(page.locator(".instructions-text")).toHaveText(
    instructions.content,
  );
  await expect(page.getByRole("textbox")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Save" })).toHaveCount(0);
  await page.getByRole("button", { name: "Claims queue", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Open claim CLM-T420", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(region).toContainText(detail.claim.story);
});

test("read failures and missing claims have explicit retry rather than false empty states", async ({
  page,
}) => {
  await page.route("**/api/claims", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Queue connection unavailable" },
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText(
    "Queue connection unavailable",
  );
  await expect(page.getByText("There are no claims in the queue.")).toHaveCount(
    0,
  );
  await page.unroute("**/api/claims");
  await page.getByRole("button", { name: "Retry queue" }).click();
  await page.route("**/api/claims/CLM-T420", (route) =>
    route.fulfill({ status: 404, json: { detail: "Claim not found" } }),
  );
  await page
    .getByRole("button", { name: "Open claim CLM-T420", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Claim not found");
  await expect(page.getByRole("region", { name: "Claim details" })).toHaveCount(
    0,
  );
  await page.unroute("**/api/claims/CLM-T420");
  await page.getByRole("button", { name: "Retry claim" }).click();
  await expect(
    page.getByRole("region", { name: "Claim details" }),
  ).toContainText("CLM-T420");
});

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
]) {
  for (const colorScheme of ["light", "dark"] as const) {
    test(`workspace is usable at ${String(viewport.width)} in ${colorScheme} mode`, async ({
      page,
    }, testInfo) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => {
        errors.push(error.message);
      });
      page.on("console", (message) => {
        if (message.type() === "error") errors.push(message.text());
      });
      page.on("requestfailed", (req) => {
        if (req.failure()?.errorText !== "net::ERR_ABORTED")
          errors.push(req.url());
      });
      await page.setViewportSize(viewport);
      await page.emulateMedia({ colorScheme });
      await page.goto("/");
      const claim = page.getByRole("button", {
        name: "Open claim CLM-T420",
        exact: true,
      });
      await claim.focus();
      await expect(claim).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(
        page.getByRole("region", { name: "Claim details" }),
      ).toBeVisible();
      for (const summary of await page.locator(".claim-detail summary").all())
        await summary.click();
      await expect
        .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
        .toBeLessThanOrEqual(viewport.width);
      await expect(page.locator(".queue-panel")).toHaveCSS(
        "background-color",
        colorScheme === "light" ? "rgb(255, 255, 255)" : "rgb(0, 0, 0)",
      );
      await page.screenshot({
        path: testInfo.outputPath("workspace.png"),
        fullPage: true,
      });
      expect(errors).toEqual([]);
    });
  }
}
