import datetime
import httpx
from enum import Enum
import asyncio
import json
from dotenv import load_dotenv
import os
from common import cookies_str_to_dict
from pydantic import BaseModel, Field

# загрузка переменных для окружения
load_dotenv()


# загружаем Юзер-Агент браузера, основной шлюз АПИ (может измениться от ГЕО!), формируем заголовки для запросов
USER_AGENT = os.getenv('USER_AGENT')
POSTFIX_URL_API = os.getenv('POSTFIX_URL_API')
HEADERS = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'User-Agent': USER_AGENT
}


# типы запросов (изначально было не ясно какие будут нужны)
class RequestTypes(Enum):
    """
    Предусмотренные типы запросов
    """
    GET = 'get'
    POST = 'post'


# формат ответа функции
class Response(BaseModel):
    """
    Модель ответа после опроса ресурса
    """
    status: bool = Field(description='Статус успешного или неуспешного выполнения')
    object: str | dict | None = Field(description='Строка если возвращается страница или словарь если был обработан json')


def gen_params_for_items(input_url: str, page: int) -> dict| bool:
    """
    Формирование параметров запроса для получения товаров
    """
    try:
        url_splitted = input_url.split('/')
        id_seller = url_splitted[4].split('-')[1]
        return {
            "url": f"/seller/{url_splitted[4]}/{url_splitted[5]}/",
            "layout_container": "categorySearchMegapagination",
            "layout_page_index": "3",
            "miniapp": f"seller_{id_seller}",
            "page": str(page)
        }
    except Exception:
        return False


def gen_params_for_llc_info(input_url: str) -> dict | bool:
    """
    Формирование параметров запроса для получения информации ЮЛ
    """
    try:
        url_splitted = input_url.split('/')
        id_seller = url_splitted[4].split('-')[1]
    except Exception:
        return False
    return {
        "url": "/modal/shop-in-shop-info",
        "seller_id": str(id_seller),
        "page_changed": "true"
    }


def get_url_api(domain: str) -> str:
    return f'https://{domain}{POSTFIX_URL_API}'


async def send_request(cookies_str: str, headers=None, type_: RequestTypes = RequestTypes.GET,
                       url: str = None, params: dict = None, data: dict = None, json_loads: bool = True,
                       max_attempts: int = 5, domain: str = None) -> Response | None:
    """
    Отправка запроса (дефолтная функция)
    :param cookies_str: куки
    :param headers: заголовки
    :param type_: тип запроса гет/пост
    :param url: адрес
    :param params: параметры
    :param data: тело запроса
    :param json_loads: флажок конвертации json в объект пайтон
    :param max_attempts: число попыток
    :param domain: домен для запросов по апи
    :return: статус + данные
    """
    # предварительная подготовка заголовков, куки, тела запроса
    if headers is None:
        headers = HEADERS
    if cookies_str is not None:
        cookies_dict = cookies_str_to_dict(cookies_str)
    else:
        cookies_dict = None
    if data is not None:
        data_json = json.dumps(data)
    else:
        data_json = None
    if url is None:
        url = get_url_api(domain)
    # инициализация асинхронного клиента
    async with httpx.AsyncClient() as client:
        while True:
            # проверка на число ошибок
            max_attempts -= 1
            if max_attempts <= 0:
                return Response(status=False, object=None)
            # запрос
            try:
                if type_ == RequestTypes.GET:
                    r = await client.get(url, headers=headers, cookies=cookies_dict, params=params, timeout=120)
                elif type_ == RequestTypes.POST:
                    r = await client.post(url, headers=headers, cookies=cookies_dict, params=params, data=data_json, timeout=120)
                print(f'{datetime.datetime.now()} status_code: {r.status_code}')
            except Exception:
                return Response(status=False, object=None)
            # распознавание кодов ответа сервера
            if 200 <= r.status_code <= 299:
                # with open(f'./requests_responses/request_{datetime.datetime.now().time()}.json', 'w') as f:
                #     f.write(str(r.text))
                # конвертация json в объект
                if json_loads is True:
                    try:
                        r_object = json.loads(r.text)
                    except Exception:
                        r_object = None
                else:
                    r_object = r.text
                return Response(status=True, object=r_object)
            elif 300 <= r.status_code <= 400:
                return Response(status=False, object=None)
            elif 500 <= r.status_code <= 599:
                await asyncio.sleep(5)
                continue
            else:
                return Response(status=False, object=None)
