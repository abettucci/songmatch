import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import Dashboard from "./pages/Dashboard";
import Auth from "./pages/Auth";
import { Loader2 } from "lucide-react";

const App = () => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary/20 via-secondary/20 to-accent/20">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <Routes>
      <Route 
        path="/" 
        element={user ? <Dashboard /> : <Navigate to="/auth" replace />} 
      />
      <Route 
        path="/auth" 
        element={!user ? <Auth /> : <Navigate to="/" replace />} 
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default App;
