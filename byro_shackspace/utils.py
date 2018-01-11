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


def match_transaction(transaction):
    uid, score = reference_parser(transaction.reference)
    member = None
    error = None
    try:
        if uid:
            member = Member.objects.get(member_id=uid)
    except Member.DoesNotExist:
        error = "Member does not exist"

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

def get_debitor_by_record_token(self, reference):
    reference = "".join(reference.lower().split())
    for debitor in self.debitors:
        if re.match(debitor['regex'], reference):
            return Debitor.objects.get(pk=debitor['pk'])
    return None
