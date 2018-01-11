import csv
import re
from decimal import Decimal
from datetime import datetime, date, timedelta


class TransactionLogProcessor:
    def __init__(self):
        self.debitors = Debitor.objects.all().values('pk', 'record_token', 'record_token_line_2')

        def build_regex(record_token):
            record_token = [re.escape(element) for element in record_token.lower().split()]
            regex = r".*" + r'\s*'.join(record_token) + ".*"
            return regex

        for i in range(len(self.debitors)):
            self.debitors[i]['regex'] = build_regex(self.debitors[i]['record_token'])
            self.debitors[i]['regex_line_2'] = build_regex(self.debitors[i]['record_token_line_2'])

    def process(self, banktransaction):
        if banktransaction.data_type == 'bank_csv':
            self.process_bank_csv(banktransaction)
        else:
            self.process_accountant_csv(banktransaction)

    def process_accountant_csv(self, banktransaction):
        banktransaction.status = 'wip'
        banktransaction.save()
        reader = csv.reader(open(banktransaction.data_file.file.name, encoding='iso-8859-1'),
                            delimiter=";", quotechar='"')
        reader.__next__()  # first line is meta of accountant
        header = reader.__next__()  # second line is header
        for line in reader:
            if not line:
                continue
            d = dict(zip(header, line))
            member = None
            uid = None
            error = None
            if 'Buchungstext' in d:
                members = Member.objects.filter(surname__iexact=d.get('Buchungstext'))
                if members.count() == 1:
                    member = members.first()
                    uid = member.member_id
            reference = d.get('Buchungstext')
            haben = Decimal(d.get('Umsatz Haben').replace(',', '.') or 0)
            soll = Decimal(d.get('Umsatz Soll').replace(',', '.') or 0)
            amount = haben - soll
            BankTransactionLog.objects.create(
                upload=banktransaction,
                reference=reference,
                member=member,
                error=error, score=0,
                amount=amount,
                booking_date=datetime.strptime(d.get('Datum'), '%d.%m.%Y').date(),
                is_matched=bool(uid),
                is_resolved=bool(uid),
                created_by=banktransaction.created_by
            )
            if member:
                defaults = {
                    'transaction_type': 'membership fee',
                    'amount': amount,
                    'created_by': banktransaction.created_by,
                    'payment_reference': reference
                }
                due_date = datetime.strptime(d.get('Datum'), '%d.%m.%Y').date()
                transation_hash = hashlib.sha256((';'.join(line)).encode('utf-8')).hexdigest()
                AccountTransaction.objects.update_or_create(
                    booking_type='deposit',
                    member=member,
                    due_date=due_date,
                    transaction_hash=transation_hash,
                    defaults=defaults)
        banktransaction.status = 'done'
        banktransaction.save()

    def process_bank_csv(self, banktransaction):
        banktransaction.status = 'wip'
        banktransaction.save()
        reader = csv.reader(open(banktransaction.data_file.file.name, encoding='iso-8859-1'),
                            delimiter=";", quotechar='"')
        header = reader.__next__()
        for line in reader:
            if not line:
                continue
            d = dict(zip(header, line))
            reference = ''
            for key in sorted(header):
                if key.startswith('VWZ'):
                    reference += d[key] + ' '

            uid, score = self.reference_parser(reference)
            member = None
            debitor = self.get_debitor_by_record_token(reference)
            error = None
            try:
                if uid:
                    member = Member.objects.get(member_id=uid)
            except Member.DoesNotExist:
                error = "Member does not exist"
            BankTransactionLog.objects.create(
                upload=banktransaction,
                reference=reference,
                member=member,
                debitor=debitor,
                error=error, score=score,
                amount=Decimal(d.get('Betrag').replace('.', '').replace(',', '.')),
                booking_date=datetime.strptime(d.get('Buchungstag'), '%d.%m.%Y').date(),
                transaction_owner=d.get('Auftraggeber/Empfänger'),
                is_matched=bool(uid) or bool(debitor),
                is_resolved=bool(uid) or bool(debitor),
                created_by=banktransaction.created_by
            )
            if member:
                defaults = {
                    'transaction_type': 'membership fee',
                    'amount': Decimal(d.get('Betrag').replace('.', '').replace(',', '.')),
                    'created_by': banktransaction.created_by,
                    'payment_reference': reference
                }
                due_date = datetime.strptime(d.get('Buchungstag'), '%d.%m.%Y').date()
                transation_hash = hashlib.sha256((';'.join(line)).encode('utf-8')).hexdigest()
                AccountTransaction.objects.update_or_create(
                    booking_type='deposit',
                    member=member,
                    due_date=due_date,
                    transaction_hash=transation_hash,
                    defaults=defaults)
            elif debitor:
                defaults = {
                    'amount': Decimal(d.get('Betrag').replace('.', '').replace(',', '.')),
                    'created_by': banktransaction.created_by,
                    'payment_reference': reference
                }
                due_date = datetime.strptime(d.get('Buchungstag'), '%d.%m.%Y').date()
                transation_hash = hashlib.sha256((';'.join(line)).encode('utf-8')).hexdigest()
                DistrictcourtAccountTransaction.objects.update_or_create(
                    booking_type='deposit',
                    debitor=debitor,
                    due_date=due_date,
                    transaction_hash=transation_hash,
                    defaults=defaults)

        banktransaction.status = 'done'
        banktransaction.save()

    def reference_parser(self, reference):
        reference = reference.lower()

        regexes = (
            r'.*mitgliedsbeitrag\s+id\s+(?P<ID>\d{1,4})\s.*',
            r'.*id\s+(?P<ID>\d{1,4})\smitgliedsbeitrag.*',
            r'.*id\s+(?P<ID>\d{1,4})\s.*',
            r'.*mitgliedsbeitrag.*id\s+(?P<ID>\d{1,4})\s.*',
            r'.*mitgliedsbeitrag\s+(?P<ID>\d{1,4})\s.*',
            r'.*beitrag\s+mitglied\s+(?P<ID>\d{1,4})\s.*',
            r'.*mitgliedsbeitrag.*\s+(?P<ID>\d{1,4})[^\d].*',
            r'.*id(?P<ID>\d{1,4})\s+zr\d+.*',
            r'.*id\s+(?P<ID>\d{1,4}),\s+zr\s+\d+.*',
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
