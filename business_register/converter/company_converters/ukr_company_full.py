import logging
import re
from django.conf import settings

from business_register.converter.company_converters.company import CompanyConverter
from business_register.models.company_models import (
    Assignee, BancruptcyReadjustment, Bylaw, Company, CompanyDetail, CompanyToKved,
    CompanyToPredecessor, ExchangeDataCompany, Founder, Predecessor,
    Signer, TerminationStarted
)
from data_ocean.converter import BulkCreateManager
from data_ocean.utils import (cut_first_word, format_date_to_yymmdd, get_first_word,
                              to_lower_string_if_exists)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class UkrCompanyFullConverter(CompanyConverter):

    def __init__(self):
        self.LOCAL_FILE_NAME = settings.LOCAL_FILE_NAME_UO_FULL
        self.LOCAL_FOLDER = settings.LOCAL_FOLDER
        self.CHUNK_SIZE = settings.CHUNK_SIZE_UO_FULL
        self.RECORD_TAG = 'SUBJECT'
        self.bulk_manager = BulkCreateManager()
        self.branch_bulk_manager = BulkCreateManager()
        self.all_bylaw_dict = self.put_objects_to_dict("name", "business_register", "Bylaw")
        self.all_predecessors_dict = self.put_objects_to_dict("name", "business_register", "Predecessor")
        self.all_companies_dict = {}
        self.branch_to_parent = {}
        self.all_company_founders = []
        self.founder_to_dict = {}
        self.company_detail_to_dict = {}
        self.company_to_kved_to_dict = {}
        self.signer_to_dict = {}
        self.termination_started_to_dict = {}
        self.bancruptcy_readjustment_to_dict = {}
        self.company_to_predecessor_to_dict = {}
        self.assignee_to_dict = {}
        self.exchange_data_to_dict = {}
        super().__init__()

    def save_or_get_bylaw(self, bylaw_from_record):
        if bylaw_from_record not in self.all_bylaw_dict:
            new_bylaw = Bylaw.objects.create(name=bylaw_from_record)
            self.all_bylaw_dict[bylaw_from_record] = new_bylaw
            return new_bylaw
        return self.all_bylaw_dict[bylaw_from_record]

    def save_or_get_predecessor(self, item):
        if item.xpath('NAME')[0].text not in self.all_predecessors_dict or \
                (hasattr(self.all_predecessors_dict, item.xpath('NAME')[0].text) and item.xpath('CODE')[0].text != \
                 self.all_predecessors_dict[item.xpath('NAME')[0].text].code):
            new_predecessor = Predecessor.objects.create(
                name=item.xpath('NAME')[0].text.lower(),
                edrpou=item.xpath('CODE')[0].text
            )
            self.all_predecessors_dict[item.xpath('NAME')[0].text] = new_predecessor
            return new_predecessor
        return self.all_predecessors_dict[item.xpath('NAME')[0].text]

    def extract_detail_founder_data(self, founder_info):
        info_to_list = founder_info.split(',')
        # deleting spaces between strings if exist
        info_to_list = [string.strip() for string in info_to_list]
        # getting first element that is a name
        name = info_to_list[0]
        # checking if second element is a EDRPOU code
        edrpou = info_to_list[1] if self.find_edrpou(info_to_list[1]) else None
        # checking if other element is an EDRPOU code in case if the name has commas inside
        if not edrpou:
            for string in info_to_list:
                if self.find_edrpou(string):
                    edrpou = string
                    # getting the name with commas inside
                    info_to_new_list = founder_info.split(string)
                    name = info_to_new_list[0]
                    logger.warning(f'Нестандартний запис: {founder_info}')
                    break
        equity = None
        element_with_equity = None
        # usually equity is at the end of the record
        for string in info_to_list:
            if string.startswith('розмір внеску до статутного фонду') and string.endswith('грн.'):
                element_with_equity = string
                equity = float(re.findall('\d+\.\d+', string)[0])
                break
        # deleting all info except the address
        address = founder_info.replace(name, '')
        if edrpou:
            address = address.replace(edrpou, '')
        if element_with_equity:
            address = address.replace(element_with_equity, '')
        if address and len(address) < 15:
            address = None
        if address and len(address) > 200:
            logger.warning(f'Завелика адреса: {address} із запису: {founder_info}')
        return name, edrpou, address, equity

    def extract_founder_data(self, founder_info):
        # split by first comma that usually separates name and equity that also has comma
        info_to_list = founder_info.split(',', 1)
        info_to_list = [string.strip() for string in info_to_list]
        name = info_to_list[0]
        is_beneficiary = False
        if name.startswith('КІНЦЕВИЙ БЕНЕФІЦІАРНИЙ ВЛАСНИК'):
            is_beneficiary = True
        second_part = info_to_list[1]
        equity = None
        address = None
        if second_part.startswith('розмір частки'):
            digital_value = re.findall('\d+\,\d+', second_part)[0]
            equity = float(digital_value.replace(',', '.'))
        else:
            address = second_part
        return name, is_beneficiary, address, equity

    def extract_beneficiary_data(self, beneficiary_info):
        # split by first comma that usually separates name and equity that also has comma
        info_to_list = beneficiary_info.split(';', 1)
        info_to_list = [string.strip() for string in info_to_list]
        if len(info_to_list) > 2:
            name = info_to_list[0]
            country = info_to_list[1]
            address = info_to_list[2]
        else:
            name, country, address = beneficiary_info, None, None
        return name, country, address

    def add_beneficiaries(self, beneficiaries_from_record, code):
        for item in beneficiaries_from_record:
            info = item.text
            name, country, address = self.extract_beneficiary_data(info)
            if name:
                name = name.lower()
            if country:
                country = country.lower()
            already_stored = False
            if self.founder_to_dict[code]:
                for stored_founder in self.founder_to_dict[code]:
                    if stored_founder.name == name:
                        already_stored = True
                        if not stored_founder.is_beneficiary:
                            stored_founder.is_beneficiary = True
                        stored_founder.info_beneficiary = info
                        stored_founder.country = country
                        stored_founder.address = address
                        break
            if not already_stored:
                founder = Founder(
                    info_beneficiary=info,
                    name=name,
                    country=country,
                    address=address,
                    is_beneficiary=True
                )
                self.founder_to_dict[code].append(founder)

    def update_beneficiaries(self, beneficiaries_from_record, company):
        already_stored_founders = list(Founder.objects.filter(company=company))
        for item in beneficiaries_from_record:
            info = item.text
            name, country, address = self.extract_beneficiary_data(info)
            if name:
                name = name.lower()
            if country:
                country = country.lower()
            already_stored = False
            if len(already_stored_founders):
                for stored_founder in already_stored_founders:
                    if stored_founder.name == name:
                        already_stored = True
                        update_fields = []
                        if stored_founder.info_beneficiary != info:
                            stored_founder.info_beneficiary = info
                            update_fields.append('info_beneficiary')
                            if not stored_founder.is_beneficiary:
                                stored_founder.is_beneficiary = True
                                update_fields.append('is_beneficiary')
                            if address and stored_founder.address != address:
                                stored_founder.address = address
                                update_fields.append('address')
                            if stored_founder.country != country:
                                stored_founder.country = country
                                update_fields.append('country')
                            if update_fields:
                                update_fields.append('updated_at')
                                stored_founder.save(update_fields=update_fields)
                        break
            if not already_stored:
                founder = Founder(
                    company=company,
                    info_beneficiary=info,
                    name=name,
                    country=country,
                    address=address,
                    is_beneficiary=True
                )
                self.bulk_manager.add(founder)

    def add_founders(self, founders_from_record, code):
        founders = []
        for item in founders_from_record:
            info = item.text
            # checking if field contains data
            if not info or info.endswith('ВІДСУТНІЙ'):
                continue
            # checking if there is additional data except name
            if ',' in item.text:
                name, edrpou, address, equity = self.extract_detail_founder_data(item.text)
                name = name.lower()
            else:
                name = item.text.lower()
                edrpou, equity, address = None, None, None
            is_beneficiary = False
            founder = Founder(
                info=info,
                name=name,
                edrpou=edrpou,
                address=address,
                equity=equity,
                is_beneficiary=is_beneficiary,
                is_founder=True
            )
            founders.append(founder)
        self.founder_to_dict[code].extend(founders)

    def update_founders(self, founders_from_record, company):
        already_stored_founders = list(Founder.objects.filter(company=company))
        for item in founders_from_record:
            info = item.text
            # checking if field contains data
            if not info or info.endswith('ВІДСУТНІЙ'):
                continue
            # checking if there is additional data except name
            if ',' in item.text:
                name, is_beneficiary, address, equity = self.extract_founder_data(item.text)
                name = name.lower()
            else:
                name = item.text.lower()
                equity, address = None, None
                is_beneficiary = False
            already_stored = False
            if len(already_stored_founders):
                for stored_founder in already_stored_founders:
                    if stored_founder.name == name:
                        already_stored = True
                        if stored_founder.info != info:
                            update_fields = []
                            stored_founder.info = info
                            update_fields.append('info')
                            if stored_founder.is_beneficiary != is_beneficiary:
                                stored_founder.is_beneficiary = is_beneficiary
                                update_fields.append('is_beneficiary')
                            if address and stored_founder.address != address:
                                stored_founder.address = address
                                update_fields.append('address')
                            if equity and stored_founder.equity != equity:
                                stored_founder.equity = equity
                                update_fields.append('equity')
                            if update_fields:
                                update_fields.append('updated_at')
                                stored_founder.save(update_fields=update_fields)
                        already_stored_founders.remove(stored_founder)
                        break
            if not already_stored:
                founder = Founder(
                    company=company,
                    info=info,
                    name=name,
                    address=address,
                    equity=equity,
                    is_beneficiary=is_beneficiary,
                    is_founder=True
                )
                self.bulk_manager.add(founder)
        if len(already_stored_founders):
            for outdated_founder in already_stored_founders:
                outdated_founder.soft_delete()

    def add_company_detail(self, founding_document_number, executive_power, superior_management,
                           managing_paper, terminated_info, termination_cancel_info, vp_dates,
                           code):
        company_detail = CompanyDetail()
        company_detail.founding_document_number = founding_document_number
        company_detail.executive_power = executive_power
        company_detail.superior_management = superior_management
        company_detail.managing_paper = managing_paper
        company_detail.terminated_info = terminated_info
        company_detail.termination_cancel_info = termination_cancel_info
        company_detail.vp_dates = vp_dates
        self.company_detail_to_dict[code] = company_detail

    def update_company_detail(self, founding_document_number, executive_power, superior_management,
                              managing_paper, terminated_info, termination_cancel_info, vp_dates,
                              company):
        company_detail = CompanyDetail.objects.filter(company=company).first()
        if company_detail:
            update_fields = []
            if company_detail.founding_document_number != founding_document_number:
                company_detail.founding_document_number = founding_document_number
                update_fields.append('founding_document_number')
            if company_detail.executive_power != executive_power:
                company_detail.executive_power = executive_power
                update_fields.append('executive_power')
            if company_detail.superior_management != superior_management:
                company_detail.superior_management = superior_management
                update_fields.append('superior_management')
            if company_detail.managing_paper != managing_paper:
                company_detail.managing_paper = managing_paper
                update_fields.append('managing_paper')
            if company_detail.terminated_info != terminated_info:
                company_detail.terminated_info = terminated_info
                update_fields.append('terminated_info')
            if company_detail.termination_cancel_info != termination_cancel_info:
                company_detail.termination_cancel_info = termination_cancel_info
                update_fields.append('termination_cancel_info')
            if company_detail.vp_dates != vp_dates:
                company_detail.vp_dates = vp_dates
                update_fields.append('vp_dates')
            if len(update_fields):
                update_fields.append('updated_at')
                company_detail.save(update_fields=update_fields)
        else:
            company_detail = CompanyDetail()
            company_detail.founding_document_number = founding_document_number
            company_detail.executive_power = executive_power
            company_detail.superior_management = superior_management
            company_detail.managing_paper = managing_paper
            company_detail.terminated_info = terminated_info
            company_detail.termination_cancel_info = termination_cancel_info
            company_detail.vp_dates = vp_dates
            company_detail.company = company
            self.bulk_manager.add(company_detail)

    def add_assignees(self, assignees_from_record, code):
        assignees = []
        for item in assignees_from_record:
            assignee = Assignee()
            if item.xpath('NAME')[0].text:
                assignee.name = item.xpath('NAME')[0].text.lower()
            assignee.edrpou = item.xpath('CODE')[0].text
            assignees.append(assignee)
        self.assignee_to_dict[code] = assignees

    def update_assignees(self, assignees_from_record, company):
        already_stored_assignees = list(Assignee.objects.filter(company=company))
        for item in assignees_from_record:
            name = item.xpath('NAME')[0].text
            if name:
                name = name.lower()
            edrpou = item.xpath('CODE')[0].text
            already_stored = False
            if len(already_stored_assignees):
                for stored_assignee in already_stored_assignees:
                    if stored_assignee.name == name and stored_assignee.edrpou == edrpou:
                        already_stored = True
                        already_stored_assignees.remove(stored_assignee)
                        break
            if not already_stored:
                assignee = Assignee()
                assignee.name = name
                assignee.edrpou = edrpou
                assignee.company = company
                self.bulk_manager.add(assignee)
        if len(already_stored_assignees):
            for outdated_assignees in already_stored_assignees:
                outdated_assignees.soft_delete()

    def add_bancruptcy_readjustment(self, record, code):
        bancruptcy_readjustment = BancruptcyReadjustment()
        bancruptcy_readjustment.op_date = format_date_to_yymmdd(
            record.xpath('BANKRUPTCY_READJUSTMENT_INFO/OP_DATE')[0].text) or None
        bancruptcy_readjustment.reason = record.xpath(
            'BANKRUPTCY_READJUSTMENT_INFO/REASON')[0].text.lower()
        bancruptcy_readjustment.sbj_state = record.xpath(
            'BANKRUPTCY_READJUSTMENT_INFO/SBJ_STATE')[0].text.lower()
        if record.xpath('BANKRUPTCY_READJUSTMENT_INFO/BANKRUPTCY_READJUSTMENT_HEAD_NAME'):
            head_name = record.xpath('BANKRUPTCY_READJUSTMENT_INFO/BANKRUPTCY_READJUSTMENT_HEAD_NAME')[0].text
            if head_name:
                bancruptcy_readjustment.head_name = head_name.lower()
        self.bancruptcy_readjustment_to_dict[code] = bancruptcy_readjustment

    def update_bancruptcy_readjustment(self, record, company):
        already_stored_bancruptcy_readjustment = BancruptcyReadjustment.objects.filter(company=company).first()
        if record.xpath('BANKRUPTCY_READJUSTMENT_INFO/OP_DATE'):
            op_date = format_date_to_yymmdd(record.xpath('BANKRUPTCY_READJUSTMENT_INFO/OP_DATE')[0].text) or None
            reason = record.xpath('BANKRUPTCY_READJUSTMENT_INFO/REASON')[0].text.lower()
            sbj_state = record.xpath('BANKRUPTCY_READJUSTMENT_INFO/SBJ_STATE')[0].text.lower()
            if record.xpath('BANKRUPTCY_READJUSTMENT_INFO/BANKRUPTCY_READJUSTMENT_HEAD_NAME'):
                head_name = record.xpath('BANKRUPTCY_READJUSTMENT_INFO/BANKRUPTCY_READJUSTMENT_HEAD_NAME')[0].text
                if head_name:
                    head_name = head_name.lower()
            else:
                head_name = None
            if not already_stored_bancruptcy_readjustment:
                bancruptcy_readjustment = BancruptcyReadjustment()
                bancruptcy_readjustment.company = company
                bancruptcy_readjustment.op_date = op_date
                bancruptcy_readjustment.reason = reason
                bancruptcy_readjustment.sbj_state = sbj_state
                bancruptcy_readjustment.head_name = head_name
                self.bulk_manager.add(bancruptcy_readjustment)
                return
            else:
                update_fields = []
                if already_stored_bancruptcy_readjustment.op_date != op_date:
                    already_stored_bancruptcy_readjustment.op_date = op_date
                    update_fields.append('op_date')
                if already_stored_bancruptcy_readjustment.reason != reason:
                    already_stored_bancruptcy_readjustment.reason = reason
                    update_fields.append('reason')
                if already_stored_bancruptcy_readjustment.sbj_state != sbj_state:
                    already_stored_bancruptcy_readjustment.sbj_state = sbj_state
                    update_fields.append('sbj_state')
                if already_stored_bancruptcy_readjustment.head_name != head_name:
                    already_stored_bancruptcy_readjustment.head_name = head_name
                    update_fields.append('head_name')
                if len(update_fields):
                    update_fields.append('updated_at')
                    already_stored_bancruptcy_readjustment.save(update_fields=update_fields)
        elif already_stored_bancruptcy_readjustment:
            already_stored_bancruptcy_readjustment.soft_delete()

    def add_company_to_kved(self, kveds_from_record, code):
        company_to_kveds = []
        for item in kveds_from_record:
            if not item.xpath('NAME'):
                continue
            kved_code = item.xpath('CODE')[0].text
            kved_name = item.xpath('NAME')[0].text
            if not kved_name:
                continue
            if not kved_code:
                kved_code = ''
            company_to_kved = CompanyToKved()
            company_to_kved.kved = self.get_kved_from_DB(kved_code, kved_name)
            if item.xpath('PRIMARY'):
                company_to_kved.primary_kved = item.xpath('PRIMARY')[0].text == "так"
            company_to_kveds.append(company_to_kved)
        self.company_to_kved_to_dict[code] = company_to_kveds

    def update_company_to_kved(self, kveds_from_record, company):
        already_stored_company_to_kved = list(CompanyToKved.objects.filter(company=company))
        for item in kveds_from_record:
            if not item.xpath('NAME'):
                continue
            kved_code = item.xpath('CODE')[0].text
            kved_name = item.xpath('NAME')[0].text
            if not kved_name:
                continue
            if not kved_code:
                kved_code = ''
            already_stored = False
            kved_from_db = self.get_kved_from_DB(kved_code, kved_name)
            if len(already_stored_company_to_kved):
                for stored_company_to_kved in already_stored_company_to_kved:
                    if stored_company_to_kved.kved == kved_from_db:
                        already_stored = True
                        if item.xpath('PRIMARY'):
                            if stored_company_to_kved.primary_kved != (item.xpath('PRIMARY')[0].text == "так"):
                                stored_company_to_kved.primary_kved = item.xpath('PRIMARY')[0].text == "так"
                                stored_company_to_kved.save(update_fields=['primary_kved', 'updated_at'])
                        already_stored_company_to_kved.remove(stored_company_to_kved)
                        break
            if not already_stored:
                company_to_kved = CompanyToKved()
                company_to_kved.company = company
                company_to_kved.kved = kved_from_db
                if item.xpath('PRIMARY'):
                    company_to_kved.primary_kved = item.xpath('PRIMARY')[0].text == "так"
                self.bulk_manager.add(company_to_kved)
        if len(already_stored_company_to_kved):
            for outdated_company_to_kved in already_stored_company_to_kved:
                outdated_company_to_kved.soft_delete()

    def add_exchange_data(self, exchange_data_from_record, code):
        exchange_datas = []
        for item in exchange_data_from_record:
            if item.xpath('AUTHORITY_NAME') and item.xpath('AUTHORITY_NAME')[0].text:
                exchange_data = ExchangeDataCompany()
                exchange_data.authority = self.save_or_get_authority(item.xpath(
                    'AUTHORITY_NAME')[0].text)
                if item.xpath('TAX_PAYER_TYPE'):
                    taxpayer_type = item.xpath('TAX_PAYER_TYPE')[0].text
                    exchange_data.taxpayer_type = self.save_or_get_taxpayer_type(taxpayer_type)
                if item.xpath('START_DATE'):
                    exchange_data.start_date = format_date_to_yymmdd(
                        item.xpath('START_DATE')[0].text) or None
                if item.xpath('START_NUM'):
                    exchange_data.start_number = item.xpath('START_NUM')[0].text
                if item.xpath('END_DATE'):
                    exchange_data.end_date = format_date_to_yymmdd(
                        item.xpath('END_DATE')[0].text) or None
                if item.xpath('END_NUM'):
                    exchange_data.end_number = item.xpath('END_NUM')[0].text
                exchange_datas.append(exchange_data)
            self.exchange_data_to_dict[code] = exchange_datas

    def update_exchange_data(self, exchange_data_from_record, company):
        already_stored_exchange_data = list(ExchangeDataCompany.objects.filter(company=company))
        for item in exchange_data_from_record:
            if not item.xpath('NAME'):
                continue
            authority = self.save_or_get_authority(item.xpath('AUTHORITY_NAME')[0].text)
            taxpayer_type = item.xpath('TAX_PAYER_TYPE')[0].text
            start_date, end_date = None, None
            if taxpayer_type:
                taxpayer_type = self.save_or_get_taxpayer_type(taxpayer_type)
            if item.xpath('START_DATE')[0].text:
                start_date = format_date_to_yymmdd(item.xpath('START_DATE')[0].text) or None
            start_number = item.xpath('START_NUM')[0].text
            if item.xpath('END_DATE')[0].text:
                end_date = format_date_to_yymmdd(item.xpath('END_DATE')[0].text) or None
            end_number = item.xpath('END_NUM')[0].text
            already_stored = False
            if len(already_stored_exchange_data):
                for stored_exchange_data in already_stored_exchange_data:
                    if stored_exchange_data.authority == authority and stored_exchange_data.start_date == start_date:
                        already_stored = True
                        update_fields = []
                        if stored_exchange_data.start_number != start_number:
                            stored_exchange_data.start_number = start_number
                            update_fields.append('start_number')
                        if stored_exchange_data.taxpayer_type != taxpayer_type:
                            stored_exchange_data.taxpayer_type = taxpayer_type
                            update_fields.append('taxpayer_type')
                        if stored_exchange_data.end_date != end_date:
                            stored_exchange_data.end_date = end_date
                            update_fields.append('end_date')
                        if stored_exchange_data.end_number != end_number:
                            stored_exchange_data.end_number = end_number
                            update_fields.append('end_number')
                        if len(update_fields):
                            update_fields.append('updated_at')
                            stored_exchange_data.save(update_fields=update_fields)
                        already_stored_exchange_data.remove(stored_exchange_data)
            if not already_stored:
                exchange_data = ExchangeDataCompany()
                exchange_data.authority = authority
                exchange_data.taxpayer_type = taxpayer_type
                exchange_data.start_date = start_date
                exchange_data.start_number = start_number
                exchange_data.end_date = end_date
                exchange_data.end_number = end_number
                exchange_data.company = company
                self.bulk_manager.add(exchange_data)
        if len(already_stored_exchange_data):
            for outdated_exchange_data in already_stored_exchange_data:
                outdated_exchange_data.soft_delete()

    def add_company_to_predecessors(self, predecessors_from_record, code):
        company_to_predecessors = []
        for item in predecessors_from_record:
            if item.xpath('NAME')[0].text:
                company_to_predecessor = CompanyToPredecessor()
                company_to_predecessor.predecessor = self.save_or_get_predecessor(item)
                company_to_predecessors.append(company_to_predecessor)
        self.company_to_predecessor_to_dict[code] = company_to_predecessors

    def update_company_to_predecessors(self, predecessors_from_record, company):
        already_stored_company_to_predecessors = list(CompanyToPredecessor.objects.filter(company=company))
        for item in predecessors_from_record:
            if item.xpath('NAME')[0].text:
                already_stored = False
                predecessor = self.save_or_get_predecessor(item)
                if len(already_stored_company_to_predecessors):
                    for stored_predecessor in already_stored_company_to_predecessors:
                        if stored_predecessor.predecessor == predecessor:
                            already_stored = True
                            already_stored_company_to_predecessors.remove(stored_predecessor)
                            break
                if not already_stored:
                    company_to_predecessor = CompanyToPredecessor()
                    company_to_predecessor.predecessor = predecessor
                    company_to_predecessor.company = company
                    self.bulk_manager.add(company_to_predecessor)
        if len(already_stored_company_to_predecessors):
            for outdated_company_to_predecessors in already_stored_company_to_predecessors:
                outdated_company_to_predecessors.soft_delete()

    def add_signers(self, signers_from_record, code):
        signers = []
        for item in signers_from_record:
            signer = Signer()
            signer.name = item.text[:389].lower()
            self.signer_to_dict[code] = signers.append(signer)
            signers.append(signer)
        self.signer_to_dict[code] = signers

    def update_signers(self, signers_from_record, company):
        already_stored_signers = list(Signer.objects.filter(company=company))
        for item in signers_from_record:
            already_stored = False
            if len(already_stored_signers):
                for stored_signer in already_stored_signers:
                    if stored_signer.name == item.text[:389].lower():
                        already_stored = True
                        already_stored_signers.remove(stored_signer)
                        break
            if not already_stored:
                signer = Signer()
                signer.name = item.text[:389].lower()
                signer.company = company
                self.bulk_manager.add(signer)
        if len(already_stored_signers):
            for outdated_signers in already_stored_signers:
                outdated_signers.soft_delete()

    def add_termination_started(self, record, code):
        termination_started = TerminationStarted()
        if record.xpath('TERMINATION_STARTED_INFO/OP_DATE')[0].text:
            termination_started.op_date = format_date_to_yymmdd(
                record.xpath('TERMINATION_STARTED_INFO/OP_DATE')[0].text) or None
        termination_started.reason = record.xpath('TERMINATION_STARTED_INFO'
                                                  '/REASON')[0].text.lower()
        termination_started.sbj_state = record.xpath(
            'TERMINATION_STARTED_INFO/SBJ_STATE')[0].text.lower()
        if record.xpath('TERMINATION_STARTED_INFO/SIGNER_NAME'):
            signer_name = record.xpath('TERMINATION_STARTED_INFO/SIGNER_NAME')[0].text
            if signer_name:
                termination_started.signer_name = signer_name.lower()
        if record.xpath('TERMINATION_STARTED_INFO/CREDITOR_REQ_END_DATE'):
            termination_started.creditor_reg_end_date = format_date_to_yymmdd(
                record.xpath('TERMINATION_STARTED_INFO/CREDITOR_REQ_END_DATE')[0].text) or '1990-01-01'
        self.termination_started_to_dict[code] = termination_started

    def update_termination_started(self, record, company):
        already_stored_termination_started = TerminationStarted.objects.filter(company=company).first()
        if record.xpath('TERMINATION_STARTED_INFO/OP_DATE'):
            op_date = format_date_to_yymmdd(record.xpath('TERMINATION_STARTED_INFO/OP_DATE')[0].text) or None
            reason = record.xpath('TERMINATION_STARTED_INFO/REASON')[0].text.lower()
            sbj_state = record.xpath('TERMINATION_STARTED_INFO/SBJ_STATE')[0].text.lower()
            if record.xpath('TERMINATION_STARTED_INFO/SIGNER_NAME'):
                signer_name = record.xpath('TERMINATION_STARTED_INFO/SIGNER_NAME')[0].text
                if signer_name:
                    signer_name = signer_name.lower()
            else:
                signer_name = None
            if record.xpath('TERMINATION_STARTED_INFO/CREDITOR_REQ_END_DATE'):
                creditor_reg_end_date = format_date_to_yymmdd(
                    record.xpath('TERMINATION_STARTED_INFO/CREDITOR_REQ_END_DATE')[0].text) or '1990-01-01'
            else:
                creditor_reg_end_date = '1990-01-01'
            if not already_stored_termination_started:
                termination_started = TerminationStarted()
                termination_started.company = company
                termination_started.op_date = op_date
                termination_started.reason = reason
                termination_started.sbj_state = sbj_state
                termination_started.signer_name = signer_name
                termination_started.creditor_reg_end_date = creditor_reg_end_date
                self.bulk_manager.add(termination_started)
                return
            else:
                update_fields = []
                if already_stored_termination_started.op_date != op_date:
                    already_stored_termination_started.op_date = op_date
                    update_fields.append('op_date')
                if already_stored_termination_started.reason != reason:
                    already_stored_termination_started.reason = reason
                    update_fields.append('reason')
                if already_stored_termination_started.sbj_state != sbj_state:
                    already_stored_termination_started.sbj_state = sbj_state
                    update_fields.append('sbj_state')
                if already_stored_termination_started.signer_name != signer_name:
                    already_stored_termination_started.signer_name = signer_name
                    update_fields.append('signer_name')
                if already_stored_termination_started.creditor_reg_end_date != creditor_reg_end_date:
                    already_stored_termination_started.creditor_reg_end_date = creditor_reg_end_date
                    update_fields.append('creditor_reg_end_date')
                if len(update_fields):
                    update_fields.append('updated_at')
                    already_stored_termination_started.save(update_fields=update_fields)
        elif already_stored_termination_started:
            already_stored_termination_started.soft_delete()

    def save_to_db(self, records):
        for record in records:
            if record.xpath('NAME')[0].text:
                name = record.xpath('NAME')[0].text.lower()
            else:
                name = None
            edrpou = record.xpath('EDRPOU')[0].text
            if not edrpou:
                continue
            code = name + edrpou
            address = record.xpath('ADDRESS')[0].text
            founding_document_number = record.xpath('FOUNDING_DOCUMENT_NUM')[0].text
            contact_info = record.xpath('CONTACTS')[0].text
            vp_dates = record.xpath('VP_DATES')[0].text
            short_name = record.xpath('SHORT_NAME')[0].text
            if short_name:
                short_name = short_name.lower()
            executive_power = record.xpath('EXECUTIVE_POWER')[0].text
            if executive_power:
                executive_power = executive_power.lower()
            superior_management = record.xpath('SUPERIOR_MANAGEMENT')[0].text
            if superior_management:
                superior_management = superior_management.lower()
            managing_paper = record.xpath('MANAGING_PAPER')[0].text
            if managing_paper:
                managing_paper = managing_paper.lower()
            terminated_info = record.xpath('TERMINATED_INFO')[0].text
            if terminated_info:
                terminated_info = terminated_info.lower()
            termination_cancel_info = record.xpath('TERMINATION_CANCEL_INFO')[0].text
            if termination_cancel_info:
                termination_cancel_info = termination_cancel_info.lower()
            authorized_capital = record.xpath('AUTHORIZED_CAPITAL')[0].text
            if authorized_capital:
                authorized_capital = authorized_capital.replace(',', '.')
                authorized_capital = float(authorized_capital)
            registration_date = None
            registration_info = None
            registration = record.xpath('REGISTRATION')[0].text
            if registration:
                registration_date = format_date_to_yymmdd(get_first_word(registration))
                registration_info = cut_first_word(registration)
            company_type = record.xpath('OPF')[0].text
            if company_type:
                company_type = self.save_or_get_company_type(company_type, 'uk')
            status = self.save_or_get_status(record.xpath('STAN')[0].text)
            bylaw = self.save_or_get_bylaw(record.xpath('STATUTE')[0].text)
            authority = record.xpath('CURRENT_AUTHORITY')[0].text
            if authority:
                authority = self.save_or_get_authority(authority)

            company = Company.objects.filter(code=code).first()

            if not company:
                company = Company(
                    name=name,
                    short_name=short_name,
                    company_type=company_type,
                    edrpou=edrpou,
                    address=address,
                    authorized_capital=authorized_capital,
                    status=status,
                    bylaw=bylaw,
                    registration_date=registration_date,
                    registration_info=registration_info,
                    contact_info=contact_info,
                    authority=authority,
                    code=code
                )
                self.bulk_manager.add(company)
                self.add_company_detail(founding_document_number, executive_power, superior_management, managing_paper,
                                        terminated_info, termination_cancel_info, vp_dates, code)
                if len(record.xpath('ACTIVITY_KINDS')[0]):
                    self.add_company_to_kved(record.xpath('ACTIVITY_KINDS')[0], code)
                if len(record.xpath('SIGNERS')[0]):
                    self.add_signers(record.xpath('SIGNERS')[0], code)
                if record.xpath('TERMINATION_STARTED_INFO/OP_DATE'):
                    self.add_termination_started(record, code)
                if record.xpath('BANKRUPTCY_READJUSTMENT_INFO/OP_DATE'):
                    self.add_bancruptcy_readjustment(record, code)
                if len(record.xpath('PREDECESSORS')[0]):
                    self.add_company_to_predecessors(record.xpath('PREDECESSORS')[0], code)
                if len(record.xpath('ASSIGNEES')[0]):
                    self.add_assignees(record.xpath('ASSIGNEES')[0], code)
                if len(record.xpath('EXCHANGE_DATA')[0]):
                    self.add_exchange_data(record.xpath('EXCHANGE_DATA')[0], code)
                self.founder_to_dict[code] = []
                if len(record.xpath('FOUNDERS')[0]):
                    self.add_founders(record.xpath('FOUNDERS')[0], code)
                if len(record.xpath('BENEFICIARIES')[0]):
                    self.add_beneficiaries(record.xpath('BENEFICIARIES')[0], code)
            else:
                update_fields = []
                if company.name != name:
                    company.name = name
                    update_fields.append('name')
                if company.short_name != short_name:
                    company.short_name = short_name
                    update_fields.append('short_name')
                if company.company_type != company_type:
                    company.company_type = company_type
                    update_fields.append('company_type')
                if company.authorized_capital != authorized_capital:
                    company.authorized_capital = authorized_capital
                    update_fields.append('authorized_capital')
                if company.address != address:
                    company.address = address
                    update_fields.append('address')
                if company.status != status:
                    company.status = status
                    update_fields.append('status')
                if company.bylaw != bylaw:
                    company.bylaw = bylaw
                    update_fields.append('bylaw')
                if to_lower_string_if_exists(company.registration_date) != registration_date:
                    company.registration_date = registration_date
                    update_fields.append('registration_date')
                if company.registration_info != registration_info:
                    company.registration_info = registration_info
                    update_fields.append('registration_info')
                if company.contact_info != contact_info:
                    company.contact_info = contact_info
                    update_fields.append('contact_info')
                if company.authority != authority:
                    company.authority = authority
                    update_fields.append('authority')
                if update_fields:
                    update_fields.append('updated_at')
                    company.save(update_fields=update_fields)
                self.update_company_detail(founding_document_number, executive_power, superior_management,
                                           managing_paper, terminated_info, termination_cancel_info, vp_dates, company)
                self.update_founders(record.xpath('FOUNDERS')[0], company)
                self.update_company_to_kved(record.xpath('ACTIVITY_KINDS')[0], company)
                self.update_signers(record.xpath('SIGNERS')[0], company)
                self.update_termination_started(record, company)
                self.update_bancruptcy_readjustment(record, company)
                self.update_company_to_predecessors(record.xpath('PREDECESSORS')[0], company)
                self.update_assignees(record.xpath('ASSIGNEES')[0], company)
                self.update_exchange_data(record.xpath('EXCHANGE_DATA')[0], company)
                if record.xpath('BENEFICIARIES'):
                    self.update_beneficiaries(record.xpath('BENEFICIARIES')[0], company)

        if len(self.bulk_manager.queues['business_register.Company']):
            self.bulk_manager.commit(Company)
        for company in self.bulk_manager.queues['business_register.Company']:
            code = company.code
            if code in self.founder_to_dict:
                for founder in self.founder_to_dict[code]:
                    founder.company = company
                    self.bulk_manager.add(founder)
            if code in self.signer_to_dict:
                for signer in self.signer_to_dict[code]:
                    signer.company = company
                    self.bulk_manager.add(signer)
            if code in self.assignee_to_dict:
                for assignee in self.assignee_to_dict[code]:
                    assignee.company = company
                    self.bulk_manager.add(assignee)
            if code in self.company_to_predecessor_to_dict:
                for company_to_predecessor in self.company_to_predecessor_to_dict[code]:
                    company_to_predecessor.company = company
                    self.bulk_manager.add(company_to_predecessor)
            if code in self.exchange_data_to_dict:
                for exchange_data in self.exchange_data_to_dict[code]:
                    exchange_data.company = company
                    self.bulk_manager.add(exchange_data)
            if code in self.company_to_kved_to_dict:
                for company_to_kved in self.company_to_kved_to_dict[code]:
                    company_to_kved.company = company
                    self.bulk_manager.add(company_to_kved)
            if code in self.company_detail_to_dict:
                self.company_detail_to_dict[code].company = company
                self.bulk_manager.add(self.company_detail_to_dict[code])
            if code in self.termination_started_to_dict:
                self.termination_started_to_dict[code].company = company
                self.bulk_manager.add(self.termination_started_to_dict[code])
            if code in self.bancruptcy_readjustment_to_dict:
                self.bancruptcy_readjustment_to_dict[code].company = company
                self.bulk_manager.add(self.bancruptcy_readjustment_to_dict[code])
        self.bulk_manager.commit(Founder)
        self.bulk_manager.commit(Signer)
        self.bulk_manager.commit(Assignee)
        self.bulk_manager.commit(CompanyToPredecessor)
        self.bulk_manager.commit(ExchangeDataCompany)
        self.bulk_manager.commit(CompanyToKved)
        self.bulk_manager.commit(CompanyDetail)
        self.bulk_manager.commit(TerminationStarted)
        self.bulk_manager.commit(BancruptcyReadjustment)
        self.bulk_manager.queues['business_register.Company'] = []
        self.bulk_manager.queues['business_register.Founder'] = []
        self.bulk_manager.queues['business_register.Signer'] = []
        self.bulk_manager.queues['business_register.Assignee'] = []
        self.bulk_manager.queues['business_register.CompanyToPredecessor'] = []
        self.bulk_manager.queues['business_register.ExchangeDataCompany'] = []
        self.bulk_manager.queues['business_register.CompanyToKved'] = []
        self.bulk_manager.queues['business_register.CompanyDetail'] = []
        self.bulk_manager.queues['business_register.TerminationStarted'] = []
        self.bulk_manager.queues['business_register.BancruptcyReadjustment'] = []
        self.founder_to_dict = {}
        self.company_detail_to_dict = {}
        self.company_to_kved_to_dict = {}
        self.signer_to_dict = {}
        self.termination_started_to_dict = {}
        self.bancruptcy_readjustment_to_dict = {}
        self.company_to_predecessor_to_dict = {}
        self.assignee_to_dict = {}
        self.exchange_data_to_dict = {}
