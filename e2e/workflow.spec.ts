import { expect, test, type Page } from "@playwright/test";

async function openClaim(page: Page, id: string) {
  await page.goto("/");
  await page
    .getByRole("button", { name: `Open claim ${id}`, exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Claim details" }),
  ).toContainText(id);
}

async function start(page: Page) {
  await page.getByRole("button", { name: "Run agent", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Claim details" }),
  ).toContainText("In progress");
  await expect(page.locator(".activity-list li").first()).toBeVisible();
}

test("ordinary approval shows live activity and payment without reloading", async ({
  page,
}) => {
  await openClaim(page, "CLM-T420");
  await start(page);
  await expect(
    page.getByText("Simulated payment recorded", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".decision-panel")).toContainText("Approved");
  await expect(page.locator(".decision-heading")).toContainText("$420.00");
  await expect(page.locator(".policy-citation")).toHaveText(
    "Policy sections 3, 10",
  );
  await expect(page.locator(".activity-list")).toContainText(
    "Agent run completed",
  );
  await page.reload();
  await page
    .getByRole("button", { name: "Open claim CLM-T420", exact: true })
    .click();
  await expect(
    page.getByText("Simulated payment recorded", { exact: true }),
  ).toBeVisible();
});

test("exact threshold pays without sign-off", async ({ page }) => {
  await openClaim(page, "CLM-T1000");
  await start(page);
  await expect(
    page.getByText("Simulated payment recorded", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".decision-heading")).toContainText("$1,000.00");
  await expect(page.getByLabel("Handler", { exact: true })).toHaveCount(0);
});

test("over-limit guard, rejected sign-off and payment recovery preserve attribution", async ({
  page,
  request,
}) => {
  await openClaim(page, "CLM-T100001");
  await start(page);
  await expect(
    page.getByRole("region", { name: "Claim details" }),
  ).toContainText("Waiting for sign-off");
  const blocked = await request.post("/api/claims/CLM-T100001/pay", {
    data: { amount: "1000.01" },
  });
  expect(blocked.status()).toBe(409);
  await expect(
    page.getByText("Simulated payment recorded", { exact: true }),
  ).toHaveCount(0);
  const mutations: string[] = [];
  page.on("request", (req) => {
    if (req.method() === "POST") mutations.push(new URL(req.url()).pathname);
  });
  await page.getByLabel("Handler", { exact: true }).selectOption("HND-01");
  await page.route(
    "**/CLM-T100001/sign-off",
    (route) =>
      route.fulfill({
        status: 403,
        json: { detail: "Handler rejected for test" },
      }),
    { times: 1 },
  );
  await page
    .getByRole("button", { name: "Sign off and record payment" })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Handler rejected for test",
  );
  expect(mutations).toEqual(["/api/claims/CLM-T100001/sign-off"]);
  await page.route(
    "**/CLM-T100001/pay",
    (route) =>
      route.fulfill({
        status: 503,
        json: { detail: "Payment connection unavailable" },
      }),
    { times: 1 },
  );
  await page
    .getByRole("button", { name: "Sign off and record payment" })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Payment connection unavailable",
  );
  await expect(page.locator(".decision-panel")).toContainText("HND-01");
  await expect(
    page.getByText("Simulated payment recorded", { exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Retry payment" }).click();
  await expect(
    page.getByText("Simulated payment recorded", { exact: true }),
  ).toBeVisible();
  expect(mutations).toEqual([
    "/api/claims/CLM-T100001/sign-off",
    "/api/claims/CLM-T100001/sign-off",
    "/api/claims/CLM-T100001/pay",
    "/api/claims/CLM-T100001/pay",
  ]);
  await expect(page.locator(".decision-heading")).toContainText("$1,000.01");
  await page.reload();
  await page
    .getByRole("button", { name: "Open claim CLM-T100001", exact: true })
    .click();
  await expect(page.locator(".decision-panel")).toContainText("HND-01");
  await expect(
    page.getByText("Simulated payment recorded", { exact: true }),
  ).toBeVisible();
});

for (const [id, outcome, sections] of [
  ["CLM-TDECLINE", "Declined", "4"],
  ["CLM-TREFER", "Referred", "7, 11"],
]) {
  test(`${outcome} is decided without a payment or sign-off action`, async ({
    page,
  }) => {
    await openClaim(page, id);
    await start(page);
    await expect(page.locator(".decision-panel")).toContainText(outcome);
    await expect(page.locator(".decision-heading")).toContainText("$0.00");
    await expect(page.locator(".policy-citation")).toHaveText(
      `Policy sections ${sections}`,
    );
    await expect(
      page.getByRole("region", { name: "Claim details" }),
    ).toContainText("Decided");
    await expect(
      page.getByText("No payment is due.", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Claim actions" }).getByRole("button"),
    ).toHaveCount(0);
  });
}

test("failed baggage attempt retains history and succeeds only after explicit retry", async ({
  page,
}) => {
  await openClaim(page, "CLM-TBAG");
  await page.getByRole("button", { name: "Run agent", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Simulated agent failure",
  );
  await expect(
    page.getByRole("region", { name: "Claim details" }),
  ).toContainText("Waiting");
  await expect(page.locator(".decision-panel")).toContainText(
    "Waiting for an agent decision.",
  );
  await page.getByRole("button", { name: "Retry agent" }).click();
  await expect(
    page.getByText("Simulated payment recorded", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".decision-heading")).toContainText("$200.00");
  await expect(page.locator(".activity-list")).toContainText(
    "Simulated agent failure",
  );
});
