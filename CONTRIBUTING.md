# Contributing to this Project

We welcome contributions to this project! This document outlines the process for contributing and the standards we expect.

## Code of Conduct

This project follows the principles of open collaboration and respectful 
communication. We expect all contributors to:

- Be respectful and inclusive in all interactions
- Focus on constructive feedback and solutions
- Help maintain a welcoming environment for all contributors
- Follow professional communication standards

## Development Workflow

### Fork, Branch, and Pull Request Model

1. **Fork the Repository**: Create your own fork of the project
2. **Create a Feature Branch**: Always work on a dedicated branch
3. **Make Your Changes**: Implement your feature or fix
4. **Submit a Pull Request**: Open a PR with a clear description

### Branch Naming

Use descriptive branch names that indicate the type of change:

- `feat/add-anomaly-detection` - New features
- `fix/metric-extraction-bug` - Bug fixes  
- `docs/update-api-reference` - Documentation updates
- `refactor/simplify-adapter-interface` - Code refactoring
- `test/add-integration-tests` - Test additions

### Staying Updated

- Keep your local `main` branch synchronized with upstream
- Rebase feature branches on the latest `main` before submitting PRs
- Resolve any merge conflicts locally before pushing

## Coding Standards

### Code Formatting

This project enforces strict code style:

```bash
# Install formatting tools
pip install black isort flake8 mypy

# Format your code before committing
black src/ tests/
isort src/ tests/

# Check for linting issues
flake8 src/ tests/
mypy src/
```

### Code Quality Requirements

- **Line Length**: Maximum 88 characters (follows Black formatter)
- **Type Hints**: All public functions must have type annotations
- **Docstrings**: All public classes and functions require docstrings
- **Error Handling**: Proper exception handling with specific error types
- **Testing**: New code must include appropriate unit tests

### Documentation

- **Code Comments**: Explain complex logic and business rules
- **API Documentation**: Update tool specifications for any API changes
- **README Updates**: Keep installation and usage instructions current
- **Plugin Specs**: Update plugin specifications for new dataset types

## Testing Requirements

### Test Coverage

- **Unit Tests**: Required for all new functions and classes
- **Integration Tests**: Required for new tools and adapters
- **Fixture Data**: Provide realistic test data for new dataset types
- **Edge Cases**: Test error conditions and boundary cases

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=html

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
```

### Test Data

- Use the `tests/fixtures/` directory for sample data
- Ensure test data is realistic but doesn't contain sensitive information
- Document the purpose and structure of fixture files

## Commit Standards

### Commit Messages

Use clear, descriptive commit messages following this format:

```
<type>(<scope>): <description>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (no logic changes)
- `refactor`: Code refactoring
- `test`: Test additions or modifications
- `chore`: Maintenance tasks

**Examples:**
```
feat(plugins): add anomaly detection to performance plugin

Implement statistical anomaly detection using z-score and IQR methods.
Configurable sensitivity levels and support for multiple metrics.

Closes #123
AI-assisted-by: Claude Sonnet 4

fix(adapters): handle connection timeout in generic Source MCP adapter

Add exponential backoff retry logic for connection failures.
Improves reliability when Source MCP backend is under load.

AI-assisted-by: Claude Sonnet 4
```

### AI-Assisted Development

When AI agents assist with development work, include this tag in commit messages:

```
AI-assisted-by: <AI agent model(s)>
```

Examples:
- `AI-assisted-by: Claude Sonnet 4`
- `AI-assisted-by: GPT-4, GitHub Copilot`

## Pull Request Process

### Before Submitting

1. **Run the full test suite**: Ensure all tests pass
2. **Check code formatting**: Run Black, isort, and flake8
3. **Update documentation**: Include any necessary doc updates
4. **Add changelog entry**: Update relevant documentation
5. **Rebase on main**: Ensure clean commit history

### PR Description Template

```markdown
## Description
Brief description of the changes and their purpose.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that causes existing functionality to change)
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass  
- [ ] Added new tests for this change
- [ ] Manual testing completed

## Checklist
- [ ] Code follows the project's style guidelines
- [ ] Self-review completed
- [ ] Code is properly commented
- [ ] Documentation updated
- [ ] No new warnings or errors introduced

## Related Issues
Fixes #(issue number)
```

### Review Process

1. **Automated Checks**: CI pipeline runs tests and linting
2. **Peer Review**: At least one maintainer review required
3. **Documentation Review**: Check for doc completeness
4. **Testing Review**: Verify test coverage and quality
5. **Final Approval**: Maintainer approval before merge

## Development Setup

### Prerequisites

- Python 3.11+
- Git
- Access to a Source MCP instance (for integration tests)

### Local Development

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/your-domain-mcp-project.git
cd your-domain-mcp-project

# Set up Python environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Set up pre-commit hooks (optional but recommended)
pre-commit install

# Run tests to verify setup
pytest
```

### Environment Configuration

Create a `.env` file for local testing:

```env
# Copy from .env.example and customize
# Example for Horreum Source MCP
HORREUM_MCP_ENDPOINT=http://localhost:3001
HORREUM_MCP_TOKEN=your-test-token
# Example for Elasticsearch Source MCP (using mcp-server-elasticsearch)
ELASTICSEARCH_MCP_COMMAND="uvx mcp-server-elasticsearch"
ELASTICSEARCH_MCP_ARGS="--es-url http://localhost:9200"
DOMAIN_MCP_LOG_LEVEL=DEBUG
```

## Project Structure

Understanding the codebase structure:

```
src/
├── server/           # MCP server implementation
├── adapters/         # Source MCP adapters
├── domain/
│   ├── plugins/      # Dataset-type plugins
│   ├── examples/     # Reference plugin implementations
│   ├── aggregators/  # Statistical analysis
│   └── reports/      # Report templates
├── observability/    # Metrics, tracing, logging
└── config/          # Configuration management

tests/
├── unit/            # Unit tests
├── integration/     # Integration tests
└── fixtures/        # Test data

docs/
├── plugins/         # Plugin specifications
├── contracts/       # API contracts
├── api/            # Tool documentation
└── deployment/     # Deployment guides
```

## Plugin Development

### Adding New Dataset Types

1. **Create Plugin Specification**: Document in `docs/plugins/`
2. **Implement Plugin Class**: Add to `src/domain/plugins/`
3. **Add Test Fixtures**: Create sample data in `tests/fixtures/`
4. **Write Tests**: Unit and integration tests
5. **Update Documentation**: API docs and README

### Plugin Interface

All plugins must implement:

```python
class DatasetPlugin:
    def matches(self, dataset_ref: DomainDatasetRef) -> bool:
        """Check if plugin can handle this dataset"""
        
    async def extract(self, dataset: DomainDataset) -> List[MetricPoint]:
        """Extract metrics from dataset"""
```

## Getting Help

### Resources

- **Documentation**: Check the `docs/` directory
- **Development Plan**: See `IMPLEMENTATION_PLAN.md`
- **Plugin Specs**: Review `docs/plugins/` for examples
- **Source Contract**: Understand `docs/contracts/source-mcp-contract.md`

### Communication

- **Issues**: Report bugs and request features via your project's issue tracker (GitHub Issues)
- **Merge Requests**: Discuss implementation details in PR comments
- **Questions**: Use your project's issue tracker with a "question" label or similar

## Recognition

We appreciate all contributions! Contributors will be:

- Listed in project acknowledgments
- Credited in release notes for significant contributions
- Invited to participate in project direction discussions

## License

By contributing to this project, you agree that your contributions will be 
licensed under the Apache License, Version 2.0.

Thank you for contributing to this Project! 🚀

