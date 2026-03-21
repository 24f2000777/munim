import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import { SignJWT } from "jose";

/** Sign a plain HS256 JWT — verifiable by the backend with NEXTAUTH_SECRET */
async function signBackendToken(token: Record<string, unknown>): Promise<string> {
  const secret = new TextEncoder().encode(
    process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET ?? ""
  );
  // Use PostgreSQL UUID (dbId) as sub — this is what backend uses as user_id FK
  const sub = (token.dbId ?? token.sub) as string;
  return new SignJWT({
    sub,
    email: token.email as string,
    name:  token.name  as string,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("30d")
    .sign(secret);
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  secret: process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET,
  providers: [
    Google({
      clientId:     process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],
  pages: {
    signIn: "/login",
  },
  callbacks: {
    async jwt({ token, account }) {
      // On first sign-in OR if DB UUID not yet stored, sync with backend
      if (account?.providerAccountId || !(token as any).dbId) {
        try {
          const resp = await fetch(
            `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/sync`,
            {
              method:  "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                google_id:  account?.providerAccountId ?? (token as any).googleId,
                email:      token.email,
                name:       token.name,
                avatar_url: token.picture ?? null,
                user_type:  "smb_owner",
              }),
            }
          );
          if (resp.ok) {
            const user = await resp.json();
            // Store PostgreSQL UUID — used as `sub` in backend JWTs
            (token as any).dbId    = user.id;
            (token as any).userType = user.user_type;
          }
        } catch {
          // Backend not available — continue silently
        }
        if (account?.providerAccountId) {
          (token as any).googleId = account.providerAccountId;
        }
        if (!(token as any).userType) {
          (token as any).userType = "smb_owner";
        }
      }
      return token;
    },
    async session({ session, token }) {
      // Create a plain HS256 JWT the backend can verify with NEXTAUTH_SECRET
      const accessToken = await signBackendToken(token as Record<string, unknown>);
      (session as any).accessToken   = accessToken;
      (session.user as any).userType = token.userType ?? "smb_owner";
      return session;
    },
  },
});
