import pytest
from app.schemas.repository import RepositoryContext, RetrievedSymbol, RetrievedTest


def test_empty_repository_context():
    context = RepositoryContext()
    assert context.target_symbols == []
    assert context.dependencies == []
    assert context.related_tests == []


def test_repository_context_with_symbols():
    symbol = RetrievedSymbol(name='test_symbol', type='function', file_path='test.py', body='body')
    context = RepositoryContext(target_symbols=[symbol], dependencies=[symbol])
    assert len(context.target_symbols) == 1
    assert context.target_symbols[0].name == 'test_symbol'
    assert len(context.dependencies) == 1
    assert context.dependencies[0].name == 'test_symbol'


def test_retrieved_symbol():
    symbol = RetrievedSymbol(name='test_symbol', type='class', file_path='test_file.py', body='class TestClass: pass')
    assert symbol.name == 'test_symbol'
    assert symbol.type == 'class'
    assert symbol.file_path == 'test_file.py'
    assert symbol.body == 'class TestClass: pass'


def test_retrieved_test():
    test_obj = RetrievedTest(file_path='test_file.py', body='def test_function(): pass')
    assert test_obj.file_path == 'test_file.py'
    assert test_obj.body == 'def test_function(): pass'