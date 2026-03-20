export { auth as middleware } from "@/lib/auth";

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/upload/:path*",
    "/analysis/:path*",
    "/reports/:path*",
    "/settings/:path*",
    "/alerts/:path*",
    "/ca/:path*",
    "/clients/:path*",
  ],
};
