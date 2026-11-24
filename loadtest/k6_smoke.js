import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 15,
  duration: "30s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<250"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";

export default function () {
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);

  const health = http.get(`${BASE_URL}/api/v1/health/ready/`);
  check(health, { "health ready 200": (r) => r.status === 200 });

  const search = http.get(
    `${BASE_URL}/api/v1/flights/search/?destination=LHR&date=${tomorrow}&passengers=1`
  );
  check(search, {
    "flight search 200": (r) => r.status === 200,
    "has request id": (r) => Boolean(r.headers["X-Request-Id"]),
  });

  sleep(0.2);
}
