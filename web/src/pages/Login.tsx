import { GoogleLogin } from "@react-oauth/google";
import { login } from "../lib/api";

interface Props {
  onLogin: (token: string) => void;
}

export default function Login({ onLogin }: Props) {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      height: "100vh",
      gap: "1rem",
    }}>
      <h1>Family Office</h1>
      <p style={{ color: "#666" }}>Sign in to view your portfolio</p>
      <GoogleLogin
        onSuccess={async ({ credential }) => {
          if (!credential) return;
          try {
            const { access_token } = await login(credential);
            localStorage.setItem("token", access_token);
            onLogin(access_token);
          } catch (err) {
            console.error("Login failed:", err);
          }
        }}
        onError={() => console.error("Google Sign-In failed")}
      />
    </div>
  );
}
