# MAI — Multi-Model AI Interface

![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat&logo=next.js&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat&logo=openai&logoColor=white)
![Prisma](https://img.shields.io/badge/Prisma-2D3748?style=flat&logo=prisma&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-000000?style=flat&logo=vercel&logoColor=white)

A unified interface for interacting with **GPT-4**, **Claude**, and **Gemini** — switch between frontier AI models in a single, clean chat UI. Built with Next.js App Router, Prisma, and GitHub OAuth.

## Features

- **Multi-model routing** — switch between OpenAI GPT-4, Anthropic Claude, and Google Gemini seamlessly
- **Persistent chat history** — conversations stored in PostgreSQL via Prisma ORM
- **GitHub OAuth authentication** — secure sign-in with NextAuth.js
- **Streaming responses** — real-time token streaming from all three providers
- **Clean, minimal UI** — built with shadcn/ui and Tailwind CSS

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| Auth | NextAuth.js (GitHub Provider) |
| Database | PostgreSQL + Prisma ORM |
| AI Providers | OpenAI, Anthropic, Google Generative AI |
| UI | shadcn/ui + Tailwind CSS |
| Deployment | Vercel |

## Getting Started

### Prerequisites
- Node.js 18+
- PostgreSQL database (local or hosted)
- API keys for OpenAI, Anthropic (Claude), Google AI
- GitHub OAuth App credentials

### Installation

```bash
git clone https://github.com/bijudamian/MAI
cd MAI
npm install
```

### Environment Variables

Create a `.env.local` file in the root:

```env
DATABASE_URL=your_postgresql_url
NEXTAUTH_SECRET=your_nextauth_secret
NEXTAUTH_URL=http://localhost:3000
GITHUB_ID=your_github_oauth_id
GITHUB_SECRET=your_github_oauth_secret
OPENAI_API_KEY=your_openai_key
CLAUDE_API_KEY=your_anthropic_key
GOOGLE_AI_API_KEY=your_google_ai_key
```

### Run

```bash
npx prisma db push
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Deployment

Deploy to Vercel with one click. Set all environment variables in the Vercel dashboard. Uses Vercel Postgres or any external PostgreSQL provider.

## Architecture

```
app/
  api/
    auth/          # NextAuth route handlers
    chat/          # Streaming AI response endpoints
  chat/            # Chat UI pages
components/        # Reusable UI components
lib/               # AI provider clients, utilities
prisma/            # Database schema
```

## License

MIT — built by [Biju Damian](https://github.com/bijudamian)
