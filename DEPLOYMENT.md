# 🚀 Deployment Guide

Complete step-by-step guide to deploy SoundMatch to production.

## Prerequisites Checklist

- [ ] AWS Account with CLI configured
- [ ] Spotify Developer Account ([Get one here](https://developer.spotify.com/dashboard))
- [ ] Last.fm API Account ([Get one here](https://www.last.fm/api/account/create))
- [ ] PostgreSQL Database (Neon recommended for free tier)
- [ ] Netlify Account (for frontend hosting)
- [ ] GitHub repository (for CI/CD)

## 🗄️ Step 1: Database Setup

### Option A: Neon (Recommended - Free Tier)

1. Go to [https://neon.tech](https://neon.tech)
2. Sign up and create a new project
3. Select region closest to your users
4. Copy the connection string (looks like: `postgresql://user:pass@host.neon.tech/database`)
5. Run the schema:

```bash
psql "your_connection_string" -f infrastructure/schema.sql
```

### Option B: Railway

1. Go to [https://railway.app](https://railway.app)
2. Create a new PostgreSQL database
3. Copy the connection string
4. Run the schema (same as above)

### Option C: AWS RDS

1. Create PostgreSQL instance in AWS Console
2. Configure security group to allow Lambda access
3. Copy connection details
4. Run schema

## 🔑 Step 2: Get API Keys

### Spotify API

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Copy **Client ID** and **Client Secret**
4. Add redirect URIs if needed (not required for backend-only)

### Last.fm API

1. Go to [Last.fm API](https://www.last.fm/api/account/create)
2. Create an API account
3. Copy the **API Key**

## ⚙️ Step 3: Configure Secrets

### GitHub Secrets (for CI/CD)

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add the following secrets:

```
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
LASTFM_API_KEY=your_lastfm_api_key
DATABASE_URL=postgresql://user:pass@host:5432/database
NETLIFY_AUTH_TOKEN=your_netlify_token
NETLIFY_SITE_ID=your_netlify_site_id
```

### Get Netlify Tokens

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Login and get token
netlify login
netlify sites:create --name soundmatch

# Get site ID
netlify status
```

## 🏗️ Step 4: Deploy Backend

### Manual Deployment

```bash
# 1. Build the Lambda function
cd backend
make build

# 2. Configure Terraform variables
cd ../infrastructure
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your values
nano terraform.tfvars

# 3. Initialize Terraform
terraform init

# 4. Create a plan
terraform plan

# 5. Apply (create resources)
terraform apply

# 6. Save the API endpoint
terraform output api_endpoint
```

### Automatic Deployment (GitHub Actions)

Simply push to main branch:

```bash
git add .
git commit -m "Initial deployment"
git push origin main
```

GitHub Actions will automatically:
1. Run tests
2. Build the Go binary
3. Deploy to AWS Lambda via Terraform
4. Output the API endpoint

## 🎨 Step 5: Deploy Frontend

### Configure Frontend

```bash
# Get your API endpoint from Terraform
API_ENDPOINT=$(cd infrastructure && terraform output -raw api_endpoint)

# Create production env file
echo "VITE_API_URL=$API_ENDPOINT" > .env.production
```

### Manual Deployment

```bash
# Build
npm run build

# Deploy to Netlify
netlify deploy --prod --dir=dist
```

### Automatic Deployment

Push to main branch (if GitHub Actions is configured):

```bash
git add .
git commit -m "Deploy frontend"
git push origin main
```

## ✅ Step 6: Verify Deployment

### Test Backend

```bash
# Health check
curl https://your-api-endpoint.execute-api.us-east-1.amazonaws.com/health

# Should return: {"status":"ok"}

# Test search (no auth required)
curl -X POST https://your-api-endpoint/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Beatles","limit":5}'
```

### Test Frontend

1. Open your Netlify URL
2. Register a new account
3. Search for songs
4. Get recommendations

## 🔧 Troubleshooting

### Backend Issues

**Lambda timeout:**
```bash
# Increase timeout in infrastructure/main.tf
timeout = 60  # Changed from 30
```

**Database connection failed:**
```bash
# Check security group allows Lambda access
# Verify DATABASE_URL format
# Test connection locally first
psql $DATABASE_URL -c "SELECT 1;"
```

**Spotify API errors:**
```bash
# Verify credentials
curl -X POST https://accounts.spotify.com/api/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -u "$SPOTIFY_CLIENT_ID:$SPOTIFY_CLIENT_SECRET"
```

### Frontend Issues

**Can't connect to API:**
```bash
# Verify VITE_API_URL in .env.production
# Check CORS settings in backend
# Verify API Gateway is publicly accessible
```

**Build failures:**
```bash
# Clear cache
rm -rf node_modules dist
npm install
npm run build
```

## 📊 Monitoring Setup

### CloudWatch Alarms

```bash
# Create alarm for Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name soundmatch-lambda-errors \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=soundmatch-api-prod
```

### View Logs

```bash
# Lambda logs
aws logs tail /aws/lambda/soundmatch-api-prod --follow

# API Gateway logs
aws logs tail /aws/apigateway/soundmatch-prod --follow
```

## 🔄 Updates and Rollbacks

### Update Backend

```bash
cd backend
make build

cd ../infrastructure
terraform apply
```

### Rollback Backend

```bash
cd infrastructure

# View previous states
terraform state list

# Rollback to previous version
# (You'll need to rebuild the old version first)
terraform apply
```

### Update Frontend

```bash
npm run build
netlify deploy --prod --dir=dist
```

## 💾 Backup and Recovery

### Database Backups

```bash
# Manual backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Restore
psql $DATABASE_URL < backup_20240101.sql
```

### Automated Backups (Neon)

Neon automatically creates daily backups. Go to your Neon dashboard to manage them.

## 🔒 Security Checklist

- [ ] Environment variables are in Secrets, not in code
- [ ] Database has strong password
- [ ] API Gateway has rate limiting enabled
- [ ] CORS is properly configured
- [ ] HTTPS is enforced
- [ ] Database requires SSL connection
- [ ] Lambda has minimal IAM permissions
- [ ] CloudWatch logs retention is set
- [ ] No API keys in frontend code

## 📈 Scaling Considerations

### When to Scale

- Lambda concurrency > 80%
- Database connections > 80% of max
- Response time > 1 second
- Error rate > 1%

### Scaling Options

1. **Lambda**: Auto-scales, increase memory if needed
2. **Database**: Upgrade Neon tier or move to RDS
3. **API Gateway**: Auto-scales, no action needed
4. **Frontend**: Netlify auto-scales

## 💰 Cost Optimization

### Monitor Costs

```bash
# Get current month costs
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-02-01 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=SERVICE
```

### Optimization Tips

1. Set Lambda memory to minimum required (start with 512MB)
2. Set CloudWatch log retention to 7 days
3. Use Neon free tier for < 10k users
4. Enable Lambda function caching
5. Use CDN for frontend assets (Netlify does this automatically)

## 🎉 Done!

Your SoundMatch application is now deployed and running in production!

**Next Steps:**
- Set up monitoring and alerts
- Configure custom domain
- Set up SSL certificate (automatic with Netlify)
- Add analytics
- Create backup strategy

**Need Help?**
- Check the main README.md
- Open an issue on GitHub
- Join our community discussions

