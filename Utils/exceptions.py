"""
В данном модуле написаны кастомные исключения, которые могут возникнуть во время работы Кардинала и других подпрограмм.
"""


class SectionNotExists(Exception):
    """
    Исключение, которые райзится, когда необходимая секция отсутствует в конфиге.
    """
    def __init__(self, section_name: str, config_name: str):
        """
        :param section_name: название отсутствующей секции.
        :param config_name: название конфига.
        """
        self.section_name = section_name
        self.config_name = config_name

    def __str__(self):
        return f"Отсутствует обязательная секция \"{self.section_name}\" в конфиге {self.config_name}."


class ParamNotExists(Exception):
    """
    Исключение, которое райзится, когда необходимы параметр отсутствует в секции конфига.
    """
    def __init__(self, section_name: str, param_name: str, config_name: str):
        """
        :param section_name: название секции, в которой отсутствует нужный параметр.
        :param param_name: название параметра, который отсутствует.
        :param config_name: название конфига.
        """
        self.section_name = section_name
        self.param_name = param_name
        self.config_name = config_name
        super(ParamNotExists, self).__init__()

    def __str__(self):
        return f"Отсутствует параметр \"{self.param_name}\" в секции [{self.section_name}] " \
               f"конфига {self.config_name}"


class ParamValueEmpty(Exception):
    """
    Исключение, которое райзится, когда значение параметра пустое.
    """
    def __init__(self, section_name: str, param_name: str, config_name: str):
        """
        :param section_name: название секции, в которой пустое значение параметра.
        :param param_name: название параметра, значение которого пустое.
        :param config_name: название конфига.
        """
        self.section_name = section_name
        self.param_name = param_name
        self.config_name = config_name
        super(ParamValueEmpty, self).__init__()

    def __str__(self):
        return f"Пустое значение параметра \"{self.param_name}\" в секции [{self.section_name}] " \
               f"конфига {self.config_name}"


class ParamValueNotValid(Exception):
    """
    Исключение, которое райзится, когда значение параметра невалидно.
    """
    def __init__(self, section_name: str, param_name: str, valid_values: list[str], config_name: str):
        """
        :param section_name: название секции, в которой параметр имеет невалидное значение.
        :param param_name: название параметра.
        :param valid_values: список валидных значений.
        :param config_name: название конфига.
        """
        self.section_name = section_name
        self.param_name = param_name
        self.valid_values = valid_values
        self.config_name = config_name
        super(ParamValueNotValid, self).__init__()

    def __str__(self):
        return f"Недопустимое значение параметра \"{self.param_name}\" в секции [{self.section_name}] " \
               f"конфига {self.config_name}. Допустимые значения: {self.valid_values}."


class NoProductsError(Exception):
    """
    Исключение, которое райзится, когда в файле с товарами не осталось товаров (только при загрузке конфигов).
    """
    def __init__(self, products_file_path: str):
        """
        :param products_file_path: путь до файла с товарами.
        """
        self.products_file_path = products_file_path
        super(NoProductsError, self).__init__()

    def __str__(self):
        return f"В файле {self.products_file_path} закончились товары."


class NoProductVarError(Exception):
    """
    Исключение, которое райзится, когда в тексте ответа авто-выдачи товара нет переменной $product, но при этом
    указан products_storage_type.
    """
    def __init__(self, lot_name: str):
        """
        :param lot_name: название или псевдоним лота.
        """
        self.lot_name = lot_name
        super(NoProductVarError, self).__init__()

    def __str__(self):
        return f"В тексте ответа авто-выдачи товара [{self.lot_name}] отсутствует переменная $product."


class NoSuchProductFileError(Exception):
    """
    Исключение, которое райзится, когда файл, указанный в качетстве файла с товарами в конфиге авто-выдачи, отсутствует.
    """
    def __init__(self, lot_name: str, file_path: str):
        """
        :param lot_name: название или псевдоним лота.
        :param file_path: указанный в конфиге путь к файлу с товарами для авто-выдачи.
        """
        self.lot_name = lot_name
        self.file_path = file_path

    def __str__(self):
        return f"Файл с товарами {self.file_path} для авто-выдачи лота [{self.lot_name}] не найден."


class JSONParseError(Exception):
    """
    Исключение, которое райзится, когда райзится json.decoder.JSONDecodeError при обработке файла с товарами для
    автовыдачи.
    """
    def __init__(self, lot_name: str, file_path: str, json_error_text: str):
        """
        :param lot_name: название или псевдоним лота.
        :param file_path: указанный в конфиге путь к файлу с товарами для авто-выдачи.
        :param json_error_text: текст ошибки парсера JSON
        """
        self.lot_name = lot_name
        self.file_path = file_path
        self.json_error_text = json_error_text

    def __str__(self):
        return f"При парсинге файла {self.file_path} с товарами для автовыдачи лота [{self.lot_name}] " \
               f"произошла ошибка:\n{self.json_error_text}"
