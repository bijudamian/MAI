# Contributing to MAI

Thanks for your interest in contributing to MAI! Here's how to get started.

## Getting Started

1. Fork the repo and clone locally
2. Install dependencies: `npm install`
3. Copy `.env.example` to `.env.local` and add your API keys
4. Run dev server: `npm run dev`

## How to Contribute

### Reporting Bugs
Open an [Issue](https://github.com/bijudamian/MAI/issues) with:
- Clear title describing the bug
- Steps to reproduce
- Expected vs actual behavior
- Screenshots if applicable

### Suggesting Features
Open a [Discussion](https://github.com/bijudamian/MAI/discussions) in the Ideas category.

### Pull Requests
1. Create a branch: `git checkout -b feature/your-feature-name`
2. Make your changes with clear commit messages
3. Ensure no TypeScript errors: `npm run type-check`
4. Push and open a PR against `main`

## Code Style
- TypeScript strict mode
- Prettier formatting (`npm run format`)
- ESLint rules enforced

## Adding a New AI Model
1. Add the provider SDK to `package.json`
2. Create a handler in `lib/providers/`
3. Register it in `lib/models.ts`
4. Add the UI option in `components/ModelSelector.tsx`

## Need Help?
Join the [Discussions](https://github.com/bijudamian/MAI/discussions) or open an issue.

All contributions are welcome — code, docs, bug reports, and ideas!
