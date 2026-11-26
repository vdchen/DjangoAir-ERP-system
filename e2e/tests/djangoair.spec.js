const { test, expect } = require("@playwright/test");

test.describe("DjangoAir ERP End-to-End Browser Flows", () => {
  test("Customer 4-step booking, emulated payment decline/approve, and PDF invoice", async ({
    page,
    request,
  }) => {
    await page.goto("/");

    // Step 1: 3-input welcome screen
    await expect(page.locator("#search-destination")).toBeVisible();
    await expect(page.locator("#search-date")).toBeVisible();
    await expect(page.locator("#search-passengers")).toBeVisible();

    await page.selectOption("#search-destination", "LHR");
    await page.click("#search-submit-btn");

    // Step 2: Select first available seat class & option
    const firstSeat = page.locator(".da-seat-card").first();
    await expect(firstSeat).toBeVisible();
    await firstSeat.click();

    await page.locator('input[type="checkbox"]').first().check();
    await page.click("#continue-checkout-btn");

    // Step 3: Passenger details + emulated payment
    const uniqueEmail = `e2e.${Date.now()}@example.com`;
    await page.fill("#contact-email", uniqueEmail);

    // First test declined card (0002)
    await page.getByRole("button", { name: /Declined \(0002\)/ }).click();
    await page.click("#pay-and-book-btn");
    await expect(page.locator(".alert-danger")).toContainText(/declined/i);

    // Switch to approved card (4242) and complete booking
    await page.getByRole("button", { name: /Approved \(4242\)/ }).click();
    await page.click("#pay-and-book-btn");

    // Step 4: Confirmation screen + PDF invoice check
    await expect(page.getByText("Booking Confirmed & Paid")).toBeVisible();
    const ticketCode = (await page.locator(".da-ticket-code").first().textContent()).trim();
    expect(ticketCode).toMatch(/^DA-/);

    const invoiceHref = await page.locator("#download-invoice-pdf-btn").getAttribute("href");
    expect(invoiceHref).toMatch(/\/api\/v1\/payments\/.+\/invoice\.pdf$/);

    const pdfResp = await request.get(invoiceHref);
    expect(pdfResp.status()).toBe(200);
    expect(pdfResp.headers()["content-type"]).toContain("application/pdf");
    const pdfBuffer = await pdfResp.body();
    expect(pdfBuffer.subarray(0, 5).toString("utf-8")).toBe("%PDF-");
  });

  test("Personal Cabinet Google OAuth2 sign-in, Alice cabinet online check-in & QR PDF boarding pass", async ({
    page,
  }) => {
    await page.goto("/");
    await page.click("#nav-personal-cabinet");

    // 1. Sign in via Google OAuth2 (dev mock)
    await page.click("#google-oauth-toggle-btn");
    await page.fill("#google-mock-email", `google.e2e.${Date.now()}@gmail.com`);
    await page.click("#google-mock-submit-btn");
    await expect(page.getByText("Google Connected")).toBeVisible();

    // Sign out and sign in as seeded demo customer Alice
    await page.click("#cabinet-signout-btn");
    await page.click("#fill-demo-customer-btn");
    await page.click("#cabinet-login-btn");

    await expect(page.getByText("alice@example.com")).toBeVisible();
    await expect(page.getByText("Upcoming Flights")).toBeVisible();
    await expect(page.getByText("Previous Flights")).toBeVisible();

    // Perform online check-in if PAID
    const checkInBtn = page.getByRole("button", { name: "Online Check-In" }).first();
    if (await checkInBtn.isVisible()) {
      await checkInBtn.click();
      await expect(page.locator(".alert-success")).toContainText("Online check-in completed");
    }

    // Verify PDF Boarding Pass (QR) download triggers cleanly
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "PDF Boarding Pass (QR)" }).first().click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/^boarding-pass-DA-.*\.pdf$/);
  });

  test("Staff Portal (/staff/) enforces ascending role hierarchy (Gate < Check-in < Supervisor)", async ({
    page,
  }) => {
    await page.goto("/staff/");

    // Level 1: Gate Manager sees ONLY Gate Boarding tab
    await page.getByRole("button", { name: /Level 1 — Gate Manager/ }).click();
    await page.click("#staff-login-btn");
    await expect(page.getByRole("button", { name: /Gate Boarding \(L1\+\)/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Check-in & Luggage/ })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Supervisor Control/ })).toHaveCount(0);

    // Sign out -> Level 2: Check-in Manager sees Gate + Check-in, NOT Supervisor
    await page.getByRole("button", { name: "Sign Out" }).click();
    await page.getByRole("button", { name: /Level 2 — Check-in Manager/ }).click();
    await page.click("#staff-login-btn");
    await expect(page.getByRole("button", { name: /Gate Boarding \(L1\+\)/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Check-in & Luggage/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Supervisor Control/ })).toHaveCount(0);

    // Sign out -> Level 3: Supervisor sees all 3 tabs and can add an option
    await page.getByRole("button", { name: "Sign Out" }).click();
    await page.getByRole("button", { name: /Level 3 — Supervisor/ }).click();
    await page.click("#staff-login-btn");
    await expect(page.getByRole("button", { name: /Supervisor Control \(L3\)/ })).toBeVisible();

    const optName = `E2E Lounge ${Date.now()}`;
    await page.fill('input[placeholder*="Option name"]', optName);
    await page.getByRole("button", { name: "Add Option" }).click();
    await expect(page.getByText(optName)).toBeVisible();
  });

  test("Round-Trip search + Interactive Cabin Seat Map (Redis TTL hold) issues 2 leg tickets", async ({
    page,
  }) => {
    await page.goto("/");

    await page.click("#trip-type-roundtrip");
    await page.selectOption("#search-origin", "JFK");
    await page.selectOption("#search-destination", "LHR");
    await page.click("#search-submit-btn");

    // Select outbound seat class -> interactive cabin seat map loads
    const outboundCard = page.locator(".da-seat-card:not(.da-return-seat-card)").first();
    await expect(outboundCard).toBeVisible();
    await outboundCard.click();

    const outboundSeatBtn = page.locator(".da-seat-map-panel .da-cabin-seat:not([disabled])").first();
    await expect(outboundSeatBtn).toBeVisible();
    const chosenOutSeat = (await outboundSeatBtn.getAttribute("data-seat")).trim();
    await outboundSeatBtn.click();
    await expect(page.getByText(`Held: ${chosenOutSeat}`)).toBeVisible();

    // Select return flight seat class
    const returnCard = page.locator(".da-return-seat-card").first();
    await expect(returnCard).toBeVisible();
    await returnCard.click();

    await page.click("#continue-checkout-btn");
    await page.fill("#contact-email", `roundtrip.e2e.${Date.now()}@example.com`);
    await page.click("#pay-and-book-btn");

    await expect(page.getByText("Booking Confirmed & Paid")).toBeVisible();
    await expect(page.locator(".da-ticket-code")).toHaveCount(2);
    await expect(page.getByText(`Seat ${chosenOutSeat}`)).toBeVisible();
  });
});
