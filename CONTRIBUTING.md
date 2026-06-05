# Contributing to CairnBooks

Thank you for your interest in contributing! This document outlines the process for reporting issues, proposing features, and submitting code.

## Code of Conduct

Be respectful and constructive. We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

## How to contribute

### Reporting bugs

1. Search [existing issues](../../issues) to avoid duplicates.
2. Open a new issue with a clear title and description, steps to reproduce, and expected vs. actual behaviour.

### Proposing features

Open a GitHub Discussion or issue labelled `enhancement` before writing code. This lets the team align on scope before effort is invested.

### Submitting pull requests

1. Fork the repository and create a feature branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Keep changes focused — one logical change per PR.
3. Write tests for new behaviour.
4. Run the full test suite locally and ensure it passes.
5. Open a pull request against `main` with a clear description of *what* and *why*.

## Commit style

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add invoice PDF export
fix: correct tax rounding on line items
chore: update dependencies
docs: add setup guide
```

## Development setup

_Detailed setup instructions will be added as the project matures._

## License

By contributing you agree that your contributions will be licensed under the [MIT License](LICENSE).
