# Contributing to AST-Healing-Coder

Thank you for your interest in contributing to **AST-Healing-Coder**! 🎉

We welcome contributions, bug reports, feature requests, and documentation improvements.

---

## 🛠 Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/hicham-dev/langgraph-mcp-coding-assistant.git
   cd langgraph-mcp-coding-assistant
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install in editable mode with development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

---

## 🧪 Testing & Code Standards

Before submitting a Pull Request, please ensure all checks pass:

1. **Run Unit Tests:**
   ```bash
   pytest
   ```

2. **Run Linter & Type Checks:**
   ```bash
   ruff check .
   mypy src/
   ```

3. **Test the CLI:**
   ```bash
   ast-coder --demo
   ```

---

## 📬 Submitting a Pull Request

1. Create a feature branch: `git checkout -b feat/my-new-feature`
2. Commit your changes: `git commit -m "feat: add support for async AST patching"`
3. Push to your fork: `git push origin feat/my-new-feature`
4. Open a Pull Request on GitHub with a detailed description of your changes.

---

## 📜 Code of Conduct

Be respectful, open, and collaborative. We aim to foster an inclusive community for everyone.
