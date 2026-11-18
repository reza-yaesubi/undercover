import { expect, test } from "@playwright/test";

test("the dashboard loads the claims workspace and the API is healthy", async ({
  page,
  request,
}) => {
  const health = await request.get("/api/health");
  expect(health.ok()).toBe(true);
  expect(await health.json()).toEqual({ status: "ok" });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "UnderCover", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Claims queue", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /^Open claim/ }).first(),
  ).toBeVisible();
});
