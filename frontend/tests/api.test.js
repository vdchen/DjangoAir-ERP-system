// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createApiClient,
  defaultOffsetDate,
  defaultTomorrowDate,
  formatDateTime,
} from "../shared/api";

describe("DjangoAir shared API client & utilities", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("isolates tokens per SPA storage key and sends Authorization Bearer header", async () => {
    const customerApi = createApiClient("customer_token");
    const staffApi = createApiClient("staff_token");

    customerApi.setToken("cust-jwt-123");
    staffApi.setToken("staff-jwt-999");

    expect(customerApi.getToken()).toBe("cust-jwt-123");
    expect(staffApi.getToken()).toBe("staff-jwt-999");

    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok" }),
    });

    const data = await customerApi.request("/health/live/");
    expect(data).toEqual({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/health/live/",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer cust-jwt-123",
        }),
      })
    );

    customerApi.setToken(null);
    expect(customerApi.getToken()).toBeNull();
  });

  it("handles 204 No Content and surfaces structured DRF error details", async () => {
    const api = createApiClient("test_token");

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: async () => ({}),
    });
    expect(await api.request("/staff/options/123/", { method: "DELETE" })).toBeNull();

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 402,
      json: async () => ({ detail: "Card declined by issuing bank." }),
    });
    await expect(api.request("/payments/charge/", { method: "POST", body: {} })).rejects.toThrow(
      "Card declined by issuing bank."
    );
  });

  it("flattens field-level DRF validation errors cleanly", async () => {
    const api = createApiClient("test_token");
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ seat_number: ["Seat 12A is already taken."] }),
    });
    await expect(api.request("/bookings/", { method: "POST", body: {} })).rejects.toThrow(
      "Seat 12A is already taken."
    );
  });

  it("formats dates cleanly and computes UTC offset dates for round-trip defaults", () => {
    expect(formatDateTime(null)).toBe("—");
    expect(formatDateTime("2026-11-26T10:30:00Z")).toContain("2026");
    const tomorrow = defaultTomorrowDate();
    const plus3 = defaultOffsetDate(3);
    expect(tomorrow).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(plus3).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(new Date(plus3) > new Date(tomorrow)).toBe(true);
  });

  it("raises a descriptive error when downloadBlob receives non-OK status", async () => {
    const api = createApiClient("blob_token");
    api.setToken("jwt-abc");
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({ ok: false, status: 404 });
    await expect(api.downloadBlob("/cabinet/tickets/DA-MISS/boarding-pass.pdf", "bp.pdf")).rejects.toThrow(
      "Download failed (404)"
    );
  });
});
