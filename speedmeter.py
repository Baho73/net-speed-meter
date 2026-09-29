"""Замер скорости HTTP-загрузки: N последовательных скачиваний одного файла.

КОНТРАКТ МОДУЛЯ
  Назначение: оценить скорость загрузки с выбранного сервера по N полным скачиваниям.
  Вход:       http(s)-адрес файла; N > 0 (по умолчанию 10); таймаут сетевой операции > 0.
  Выход:      по строке на загрузку и итог: среднее время, объем в МБ, скорость в МБ/с и Мбит/с.
              МБ = 1 000 000 байт. Скорость = весь объем / суммарное время успешных загрузок.
  Успех:      загрузка засчитана, только если HTTP 200 и получены все байты из Content-Length.
  Ошибки:     сетевые и оборванные загрузки печатаются в stderr и не входят в итог.
  Код выхода: 0 - все загрузки успешны, 1 - хотя бы одна не прошла или неверные аргументы.
Только стандартная библиотека.
"""
import argparse
import http.client
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CHUNK = 64 * 1024
MB = 1_000_000  # десятичный мегабайт, как у провайдеров и в спидтестах

NET_ERRORS = (urllib.error.URLError, http.client.HTTPException, OSError)


class IncompleteDownload(Exception):
    """Сервер закрыл соединение раньше, чем отдал обещанный Content-Length."""


def fetch(url: str, timeout: float) -> tuple[float, int]:
    """Скачать url целиком. Вернуть (секунды, байты).

    timeout ограничивает каждую блокирующую операцию сети (подключение, ожидание
    очередного куска), а не всю загрузку: медленная, но живая передача не обрывается.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "net-speed-meter/1.1"})
    start = time.perf_counter()
    size = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:  # 206 и прочие: скачан не весь файл
            raise IncompleteDownload(f"HTTP {resp.status}, ожидался 200")
        expected = resp.headers.get("Content-Length")
        while chunk := resp.read(CHUNK):
            size += len(chunk)
    elapsed = time.perf_counter() - start
    if expected is not None and size != int(expected):
        raise IncompleteDownload(f"получено {size} байт из {expected}")
    if size == 0:
        raise IncompleteDownload("пустой ответ")
    return elapsed, size


def summarize(results: list[tuple[float, int]]) -> dict:
    """Средняя скорость = весь объем / все время, а не среднее скоростей."""
    total_time = sum(t for t, _ in results)
    total_bytes = sum(b for _, b in results)
    return {
        "avg_time": total_time / len(results),
        "total_mb": total_bytes / MB,
        "mb_per_s": total_bytes / MB / total_time,
    }


def http_url(value: str) -> str:
    parts = urllib.parse.urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise argparse.ArgumentTypeError("нужен адрес вида http(s)://host/path")
    return value


def positive_int(value: str) -> int:
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError("должно быть больше нуля")
    return n


def positive_float(value: str) -> float:
    x = float(value)
    if not (x > 0 and math.isfinite(x)):
        raise argparse.ArgumentTypeError("должно быть положительным числом")
    return x


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Замер скорости HTTP-загрузки файла")
    p.add_argument("url", type=http_url, help="адрес тяжелого файла, например большой картинки")
    p.add_argument("-n", "--requests", type=positive_int, default=10, help="число загрузок (по умолчанию 10)")
    p.add_argument("-t", "--timeout", type=positive_float, default=30.0,
                   help="таймаут сетевой операции, сек (по умолчанию 30)")
    args = p.parse_args(argv)

    results = []
    for i in range(1, args.requests + 1):
        try:
            t, size = fetch(args.url, args.timeout)
        except (IncompleteDownload, *NET_ERRORS) as e:
            print(f"#{i:>2}: ошибка: {e}", file=sys.stderr)
            continue
        results.append((t, size))
        print(f"#{i:>2}: {t:6.3f} с, {size / MB:7.2f} МБ, {size / MB / t:7.2f} МБ/с")

    if not results:
        print("Ни одна загрузка не прошла.", file=sys.stderr)
        return 1
    s = summarize(results)
    print("-" * 44)
    print(f"Успешных загрузок: {len(results)} из {args.requests}")
    print(f"Среднее время загрузки: {s['avg_time']:.3f} с")
    print(f"Скачано всего: {s['total_mb']:.2f} МБ")
    print(f"Средняя скорость: {s['mb_per_s']:.2f} МБ/с ({s['mb_per_s'] * 8:.1f} Мбит/с)")
    if s["total_mb"] / len(results) < 1:
        print("Файл меньше 1 МБ: на время сильно влияют DNS, TLS и задержка сервера.", file=sys.stderr)
    return 0 if len(results) == args.requests else 1


if __name__ == "__main__":
    sys.exit(main())
