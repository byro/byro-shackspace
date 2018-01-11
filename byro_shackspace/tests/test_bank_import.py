import pytest
from byro_shackspace.utils import process_bank_csv
from django.core.files.uploadedfile import InMemoryUploadedFile

from byro.bookkeeping.models import RealTransactionSource


@pytest.fixture
def bank_transaction_csv_file():
    actual_file = open('tests/fixtures/transactions.csv', encoding='iso-8859-1')
    f = InMemoryUploadedFile(
        file=actual_file,
        field_name=None,
        name='transactions.csv',
        content_type='text',
        size=len(actual_file.read()),
        charset='iso-8859-1',
    )
    return RealTransactionSource.objects.create(source_file=f)


@pytest.mark.django_db
def test_bank_import(bank_transaction_csv_file):
    assert bank_transaction_csv_file.transactions.count() == 0
    process_bank_csv(bank_transaction_csv_file)
    bank_transaction_csv_file.refresh_from_db()
    assert bank_transaction_csv_file.transactions.count() == 6
