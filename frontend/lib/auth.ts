import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

export const { handlers, auth, signIn, signOut } = NextAuth({
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
      // On first Google sign-in, sync with Munim backend
      if (account?.id_token) {
        try {
          const res = await fetch(
            `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/sync`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                id_token: account.id_token,
                email:    token.email,
                name:     token.name,
              }),
            }
          );
          if (res.ok) {
            const data = await res.json();
            token.accessToken = data.access_token;
            token.userType    = data.user_type;
          }
        } catch {
          // Backend may not be running during development — that's OK
          token.userType = "smb_owner";
        }
      }
      return token;
    },
    async session({ session, token }) {
      (session as any).accessToken   = token.accessToken;
      (session.user as any).userType = token.userType ?? "smb_owner";
      return session;
    },
  },
});
