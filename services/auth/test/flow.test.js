// End-to-end against a running server (npm run dev, with the local Postgres up):
//   AUTH_URL=http://localhost:8010 npm test
// Signs a new user up, creates an organization, invites a second user as viewer, and checks the
// JWT claims ml-backend relies on (org, role) for both.
import assert from "node:assert/strict";
import { test } from "node:test";

const BASE = process.env.AUTH_URL ?? "http://localhost:8010";
const ORIGIN = process.env.AUTH_ORIGIN ?? "http://localhost:5173";

function client() {
  let cookie = "";
  return async (path, body, method = body ? "POST" : "GET") => {
    const res = await fetch(`${BASE}/api/auth${path}`, {
      method,
      headers: { "Content-Type": "application/json", Origin: ORIGIN, ...(cookie ? { Cookie: cookie } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
    const set = res.headers.getSetCookie?.() ?? [];
    if (set.length) cookie = set.map((c) => c.split(";")[0]).join("; ");
    const text = await res.text();
    return { status: res.status, body: text ? JSON.parse(text) : null };
  };
}

const claims = (token) => JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString());

test("an owner and an invited viewer get JWTs scoped to their organization", { skip: !process.env.AUTH_URL }, async () => {
  const stamp = Date.now();
  const owner = client();
  const signUp = await owner("/sign-up/email", { email: `owner${stamp}@example.com`, password: "correct-horse-1", name: "Owner" });
  assert.equal(signUp.status, 200, JSON.stringify(signUp.body));

  const org = await owner("/organization/create", { name: `Acme ${stamp}`, slug: `acme-${stamp}` });
  assert.equal(org.status, 200, JSON.stringify(org.body));
  const ownerToken = (await owner("/token")).body.token;
  assert.deepEqual([claims(ownerToken).org, claims(ownerToken).role], [org.body.id, "owner"]);
  assert.equal(claims(ownerToken).aud, "sharp-ml-backend");

  const invite = await owner("/organization/invite-member", { email: `viewer${stamp}@example.com`, role: "viewer" });
  assert.equal(invite.status, 200, JSON.stringify(invite.body));

  const viewer = client();
  await viewer("/sign-up/email", { email: `viewer${stamp}@example.com`, password: "correct-horse-2", name: "Viewer" });
  const accepted = await viewer("/organization/accept-invitation", { invitationId: invite.body.id });
  assert.equal(accepted.status, 200, JSON.stringify(accepted.body));
  const viewerToken = (await viewer("/token")).body.token;
  assert.deepEqual([claims(viewerToken).org, claims(viewerToken).role], [org.body.id, "viewer"]);

  // a user outside the organization has no tenant in their token
  const stranger = client();
  await stranger("/sign-up/email", { email: `stranger${stamp}@example.com`, password: "correct-horse-3", name: "Stranger" });
  assert.equal(claims((await stranger("/token")).body.token).org, null);
});
