import ast
from pathlib import Path
import tokenize

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors = []
    for directory in ('src', 'tools', 'tests'):
        for path in (ROOT / directory).rglob('*.py'):
            source = path.read_text(encoding='utf-8')
            tree = ast.parse(source, filename=str(path))
            label = path.relative_to(ROOT)
            if ast.get_docstring(tree):
                errors.append(f'{label}: 不允许模块顶部说明字符串。')
            if source.startswith('#!'):
                errors.append(f'{label}: Python 文件不使用 shebang。')
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [item.name for item in node.names] if isinstance(node, ast.Import) else [node.module or '']
                    if any(name == 'unittest.mock' or name.startswith('unittest.mock.') for name in names):
                        errors.append(f'{label}:{node.lineno}: 测试需要直接验证实际行为。')
                if isinstance(node, ast.Try) and node.handlers:
                    if any(isinstance(item, (ast.Import, ast.ImportFrom)) for statement in node.body for item in ast.walk(statement)):
                        errors.append(f'{label}:{node.lineno}: 导入语句不放入异常捕获。')
            with path.open('rb') as handle:
                for token in tokenize.tokenize(handle.readline):
                    if token.type == tokenize.COMMENT and not any('\u4e00' <= char <= '\u9fff' for char in token.string):
                        errors.append(f'{label}:{token.start[0]}: 注释使用中文。')
    if errors:
        raise SystemExit('\n'.join(errors))
    print('源码规范检查通过。')


if __name__ == '__main__':
    main()
