import { expect, test } from "@playwright/test";

const STAFF = { email: "staff@e2e.test", password: "e2e staff password" };

test("contact form -> support inbox -> staff replies with a template", async ({ page }, info) => {
  const who = `Casey ${info.project.name}`;
  await page.goto("/contact");
  const form = page.getByTestId("contact-form");
  await form.getByLabel("Your name").fill(who);
  await form.getByLabel("Your email").fill("casey@example.com");
  await form.getByLabel("Topic").selectOption("return");
  await form.getByLabel("Message").fill("How do I send back the cable tray?");
  await form.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByTestId("contact-done")).toContainText("1 business day");

  await page.goto("/admin");
  await page.getByLabel("Email", { exact: true }).fill(STAFF.email);
  await page.getByLabel("Password").fill(STAFF.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Support", exact: true }).click();
  const card = page.getByTestId("support").locator("section", { hasText: who });
  await expect(card).toContainText("How do I send back the cable tray?");
  await card.getByLabel(/Template for message/).selectOption("return_how");
  await expect(card.getByLabel(`Reply to ${who}`)).toHaveValue(/14 days of delivery/);
  await card.getByRole("button", { name: "Send and close" }).click();
  await expect(page.getByTestId("support").locator("section", { hasText: who })).toHaveCount(0);
});
