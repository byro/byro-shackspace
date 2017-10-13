import json
from contextlib import suppress
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_date

from byro.bookkeeping.models import TransactionChannel, RealTransaction, VirtualTransaction, Account, AccountCategory
from byro.members.models import Member, Membership


def _import_sepa(member_data, member):
    sepa_keys = [
        'iban', 'mandate_reason', 'zip_code', 'country',
        'city', 'bic', 'address', 'fullname', 'issue_date',
        'institute', 'mandate_reference',
    ]
    for key in sepa_keys:
        setattr(member.profile_sepa, key, member_data.get(f'sepa__{key}'))
    member.profile_sepa.save()


def _import_transactions(member_data, member):
    real_transactions = member_data.get('bank_transactions')
    virtual_transactions = member_data.get('account_transactions')

    transactions = []
    for real_transaction in real_transactions:
        transactions.append(RealTransaction(
            channel=TransactionChannel.BANK,
            value_datetime=parse_date(real_transaction['booking_date']),
            amount=real_transaction['amount'],
            purpose=real_transaction['reference'],
            originator=real_transaction.get('transaction_owner') or 'imported',
            # TODO: reverses?
            importer='shackbureau',
        ))

    real_ids = [rt.pk for rt in RealTransaction.objects.bulk_create(transactions)]
    member.refresh_from_db()

    claims = [v for v in virtual_transactions if v['booking_type'] == 'fee_claim']
    inflows = [v for v in virtual_transactions if v['booking_type'] == 'deposit']

    fee_account, _ = Account.objects.get_or_create(
        account_category=AccountCategory.MEMBER_FEES,
    )
    donation_account, _ = Account.objects.get_or_create(
        account_category=AccountCategory.MEMBER_DONATION,
    )
    liability_account, _ = Account.objects.get_or_create(
        account_category=AccountCategory.LIABILITY,
    )

    transactions = []
    for claim in claims:
        transactions.append(VirtualTransaction(
            source_account=fee_account,
            destination_account=liability_account,
            member=member,
            amount=abs(Decimal(claim['amount'])),
            value_datetime=claim['due_date'],
        ))
    VirtualTransaction.objects.bulk_create(transactions)

    qs = RealTransaction.objects.filter(pk__in=real_ids)
    for inflow in inflows:
        account = fee_account if inflow['transaction_type'] == 'membership fee' else donation_account
        """
          {
            "amount": "-20.00",
            "booking_date": "2016-06-04",
            "payment_reference": "Mitgliedsbeitragsforderung 10/2014 ID -1",
            "transaction_type": "membership fee",
            "booking_type": "fee_claim",
            "due_date": "2014-10-01"
          },
        """
        try:
            real_transaction = qs.get(
                virtual_transactions__isnull=True,
                amount=abs(Decimal(inflow['amount'])),
                value_datetime=inflow['due_date'],
                purpose=inflow['payment_reference'],
            )
        except RealTransaction.DoesNotExist:
            real_transaction = None

        VirtualTransaction.objects.create(
            destination_account=account,
            source_account=liability_account,
            member=member,
            amount=abs(Decimal(inflow['amount'])),
            value_datetime=inflow['due_date'],
            real_transaction=real_transaction,
        )
        

def import_member(member_data):
    member = Member.objects.create(
        number=member_data['number'],
        name=member_data['name'],
        address=member_data['address'],
        email=member_data['email'],
    )
    memberships = member_data.get('memberships')
    last = None
    for membership in sorted(memberships, key=lambda m: m['membership_start']):
        obj = Membership.objects.create(
            member=member,
            start=parse_date(membership['membership_start']),
            amount=Decimal(membership['membership_fee_monthly'])*membership['membership_fee_interval'],
            interval=membership['membership_fee_interval'],
        )
        if last:
            last.end = obj.start - timedelta(days=1)
            last.save(update_fields=['end'])
        last = obj

    if member_data['payment_type'].lower() == 'sepa':
        _import_sepa(member_data, member)

    for key in ['birth_date', 'nick', 'phone_number']:
        value = member_data.get(f'profile__{key}')
        if value:
            setattr(member.profile_profile, key, value)
    member.profile_profile.save()
    _import_transactions(member_data, member)
    

class Command(BaseCommand):
    help = 'Imports a frab xml export'

    def add_arguments(self, parser):
        parser.add_argument('path', type=str)

    @transaction.atomic
    def handle(self, *args, **options):
        path = options.get('path')
        with open(path) as export:
            data = json.load(export)

        for member in data:
            import_member(member)
