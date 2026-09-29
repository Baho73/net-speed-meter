"""Замер скорости загрузки: N последовательных запросов к одному URL.

Печатает время и объём каждого запроса, среднее время, общий объём
и среднюю скорость в МБ/с и Мбит/с. Только стандартная библиотека.
"""
import argparse
import sys
import time
import urllib.request

CHUNK = 64 * 1024
MB = 1024 * 1024


def fetch(url: str, timeout: float, bust_cache: bool = True) -> tuple[float, int]:
    """Скачать url целиком. Вернуть (секунды, байты)."""
    # Уникальный параметр обходит кэш прокси и CDN: каждый раз качаем заново.
    if bust_cache:
        url = f"{url}{'&' if '?' in url else '?'}_nocache={time.time_ns()}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "net-speed-meter/1.0", "Cache-Control": "no-cache"},
    )
    start = time.perf_counter()
    size = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        while chunk := resp.read(CHUNK):
            size += len(chunk)
    return time.perf_counter() - start, size


def summarize(results: list[tuple[float, int]]) -> dict:
    total_time = sum(t for t, _ in results)
    total_bytes = sum(b for _, b in results)
    return {
        "avg_time": total_time / len(results),
        "total_mb": total_bytes / MB,
        "mb_per_s": total_bytes / MB / total_time if total_time else 0.0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Замер скорости интернета по скачиванию файла")
    p.add_argument("url", help="адрес тяжелого файла, например большой картинки")
    p.add_argument("-n", "--requests", type=int, default=10, help="число запросов (по умолчанию 10)")
    p.add_argument("-t", "--timeout", type=float, default=30.0, help="таймаут одного запроса, сек")
    p.add_argument("--no-cache-bust", action="store_true",
                   help="не добавлять _nocache к адресу (некоторые CDN отвечают на него 429)")
    args = p.parse_args()

    results = []
    for i in range(1, args.requests + 1):
        try:
            t, size = fetch(args.url, args.timeout, bust_cache=not args.no_cache_bust)
        except Exception as e:  # сеть: сообщаем и продолжаем, средние считаем по успешным
            print(f"#{i:>2}: ошибка: {e}")
            continue
        results.append((t, size))
        print(f"#{i:>2}: {t:6.3f} с, {size / MB:7.2f} МБ, {size / MB / t:7.2f} МБ/с")

    if not results:
        print("Ни один запрос не прошел.")
        return 1
    s = summarize(results)
    print("-" * 44)
    print(f"Успешных запросов: {len(results)} из {args.requests}")
    print(f"Среднее время запроса: {s['avg_time']:.3f} с")
    print(f"Скачано всего: {s['total_mb']:.2f} МБ")
    print(f"Средняя скорость: {s['mb_per_s']:.2f} МБ/с ({s['mb_per_s'] * 8:.1f} Мбит/с)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
