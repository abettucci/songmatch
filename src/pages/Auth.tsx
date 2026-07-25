import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import { Music } from 'lucide-react';

export default function Auth() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { signIn, signUp } = useAuth();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (isLogin) {
        await signIn(email, password);
        toast({
          title: 'Welcome back!',
          description: 'You have successfully signed in.',
        });
      } else {
        await signUp(email, password);
        toast({
          title: 'Account created!',
          description: 'You have successfully signed up.',
        });
      }
    } catch (error: any) {
      toast({
        title: isLogin ? 'Sign in failed' : 'Sign up failed',
        description: error.message || 'Please try again',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary/10 via-secondary/10 to-accent/10 p-4">
      <Card className="w-full max-w-md border border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader className="space-y-4">
          <div className="flex items-center justify-center">
            <div className="w-12 h-12 bg-gradient-to-br from-primary to-secondary rounded-xl flex items-center justify-center">
              <Music className="w-7 h-7 text-primary-foreground" />
            </div>
          </div>
          <div className="text-center">
            <CardTitle className="text-2xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
              SoundMatch
            </CardTitle>
            <CardDescription>
              {isLogin ? 'Sign in to your account' : 'Create a new account'}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>
            <Button
              type="submit"
              className="w-full bg-gradient-to-r from-primary to-secondary hover:from-primary/90 hover:to-secondary/90"
              disabled={loading}
            >
              {loading ? 'Loading...' : isLogin ? 'Sign In' : 'Sign Up'}
            </Button>
            <div className="text-center text-sm">
              <button
                type="button"
                onClick={() => setIsLogin(!isLogin)}
                className="text-primary hover:underline"
              >
                {isLogin
                  ? "Don't have an account? Sign up"
                  : 'Already have an account? Sign in'}
              </button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
