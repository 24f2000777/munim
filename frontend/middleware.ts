import { auth } from "@/lib/auth";
import { NextResponse, type NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.nextUrl.searchParams.get("token");

  // Allow WhatsApp analysis deep links with share token through without OAuth
  if (pathname.startsWith("/analysis/") && token) {
    return NextResponse.next();
  }

  return (auth as any)(request);
}

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
