import os.path

def test_file_encoding():
    filename = os.path.join(os.path.dirname(__file__), 'fixtures/transactions.csv')
    with open(filename, encoding='iso-8859-1') as fp:
        assert len(fp.read()) == 1086

