import csv
import re
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.dispatch import receiver
from django.utils.timezone import now

from byro.bookkeeping.models import RealTransaction, TransactionChannel
from byro.bookkeeping.signals import derive_virtual_transactions
from byro.members.models import Member


@transaction.atomic
def process_bank_csv(source):
    reader = csv.DictReader(open(source.source_file.name, encoding='iso-8859-1'), delimiter=';', quotechar='"')
    booking_timestamp = now()

    for line in reader:
        if not line:
            continue
        reference = ''
        for key in line.keys():
            if key.startswith('VWZ'):
                reference += line[key] + ' '

        RealTransaction.objects.create(
            channel=TransactionChannel.BANK,
            booking_datetime=booking_timestamp,
            value_datetime=datetime.strptime(line.get('Buchungstag'), '%d.%m.%Y'),
            amount=Decimal(line.get('Betrag').replace('.', '').replace(',', '.')),
            purpose=reference,
            originator=line.get('Auftraggeber/Empfänger', '<leer>'),
            importer='shack_bank_csv_importer',
            source=source,
            data=line,
        )


@receiver(derive_virtual_transactions)
def match_transaction(transaction, signal, **kwargs):
    uid, score = reference_parser(transaction.reference)
    member = None
    try:
        member = Member.objects.get(number=uid)
    except Member.DoesNotExist:
        return

    account = Account.objects.get(account_category=AccountCategory.MEMBER_FEES)
    data = {
        'amount': transaction.amount,
        'destination': account,
        'value_datetime': value_datetime,
        'member': member,
    }
    virtual_transaction = VirtualTransaction.objects.filter(**data).first()
    if virtual_transaction and virtual_transaction.real_transaction != transaction:
        raise Exception(f'RealTransaction {transaction.id} cannot be matched! There is already a VirtualTransaction ({virtual_transaction.id}) that is too similar. It is matched to RealTransaction {virtual_transaction.real_transaction.id}.')
    if not virtual_transaction:
        data['real_transaction'] = transaction
        virtual_transaction = VirtualTransaction.objects.create(**data)
    return [virtual_transaction]


def reference_parser(self, reference):
    reference = reference.lower()

    regexes = (
        r'.*mitgliedsbeitrag\s+id\s+(?P<ID>\d{1,4})\s.*',
        r'.*id\s+(?P<ID>\d{1,4})\smitgliedsbeitrag.*',
        # r'.*id\s+(?P<ID>\d{1,4})\s.*',
        r'.*mitgliedsbeitrag.*id\s+(?P<ID>\d{1,4})\s.*',
        r'.*mitgliedsbeitrag\s+(?P<ID>\d{1,4})\s.*',
        r'.*beitrag\s+mitglied\s+(?P<ID>\d{1,4})\s.*',
        r'.*mitgliedsbeitrag.*\s+(?P<ID>\d{1,4})[^\d].*',
        # r'.*id(?P<ID>\d{1,4})\s+zr\d+.*',
        # r'.*id\s+(?P<ID>\d{1,4}),\s+zr\s+\d+.*',
        r'.*mitgliedsbeitrag\s+id[.:-_](?P<ID>\d{1,4})\s.*',
    )

    for score, regex in enumerate(regexes, 1):
        hit = re.match(regex, reference)
        if hit:
            return (int(hit.groupdict().get('ID')), score)

    return (False, 99)
