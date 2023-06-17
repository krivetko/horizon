import re

def format_phones(phones):
    phones_list = [re.sub('\D', '', phone.strip()) for phone in phones.split(',') if phone.strip() != '']
    formatted_phones = []
    for phone in phones_list:
        digits_list = []
        formatted_phone = ''
        while len(phone) > 0:
            digits_list.insert(0, phone[-2:])
            phone = phone[:-2]
        if len(digits_list) <= 3:
            formatted_phone = '-'.join(digits_list)
        else:
            formatted_phone = '-' + '-'.join(digits_list[-2:])
            digits_list = digits_list[:-2]
            remainder = ''.join(digits_list)
            digits_list = []
            while len(remainder) > 0:
                digits_list.insert(0, remainder[-3:])
                remainder = remainder[:-3]
            if len(digits_list) == 1:
                formatted_phone = f'{digits_list[0]}' + formatted_phone
            else:
                if len(digits_list) == 2:
                    digits_list[0] = f'({digits_list[0]})'
                else:
                    digits_list[1] = f'({digits_list[1]})'
                formatted_phone = ' '.join(digits_list) + formatted_phone
        formatted_phones.append(formatted_phone)
    return '; '.join(formatted_phones)
