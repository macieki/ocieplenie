# Kalkulator docieplenia ściany i kosztów ogrzewania gazem

Aplikacja Streamlit do obliczania opłacalności docieplenia ściany murowanej — z kalkulacją wartości U, strat ciepła i rocznych kosztów gazu.

## Co robi?

1. **Oblicza współczynnik U (przenikania ciepła)** — definiujesz warstwy ściany (mur, tynki) i wybierasz materiał docieplenia z grubością. Aplikacja liczy U przed i po dociepleniu.
2. **Szacuje roczne straty ciepła** — na podstawie stopniodni grzania (HDD) i powierzchni ściany.
3. **Kalkuluje koszt gazu** — z uwzględnieniem aktualnych taryf MyOrlen (sprzedaż) i PSG (dystrybucja), sprawności kotła i VAT.
4. **Porównuje grubości docieplenia** — tabelka z U, kWh/rok i PLN/rok dla zakresu grubości.

## Wymagania

- Python 3.10+
- Zależności z `requirements.txt`

## Instalacja i uruchomienie lokalne

```bash
# Sklonuj repo
git clone <URL_REPO>
cd ocieplenie

# Zainstaluj zależności
pip install -r requirements.txt

# Uruchom
streamlit run python.py
```

Aplikacja otworzy się w przeglądarce pod `http://localhost:8501`.

## Deploy

### Streamlit Community Cloud (najprościej, za darmo)

1. Wrzuć kod na GitHub (publiczne lub prywatne repo).
2. Wejdź na [share.streamlit.io](https://share.streamlit.io/).
3. Podłącz repo → wskaż `python.py` jako plik główny.
4. Kliknij **Deploy** — gotowe.

### Railway / Render

1. Wrzuć kod na GitHub.
2. Utwórz nowy projekt na [Railway](https://railway.app/) lub [Render](https://render.com/).
3. Podłącz repo.
4. Ustaw **Start Command**: `streamlit run python.py --server.port $PORT --server.address 0.0.0.0`
5. Deploy automatyczny po pushu.

### Docker (VPS, dowolny hosting)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "python.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

```bash
docker build -t ocieplenie .
docker run -p 8501:8501 ocieplenie
```

### ⚠️ Vercel — NIE działa

Vercel obsługuje statyczne strony i serverless functions (Node.js/Python edge). Streamlit wymaga stałego serwera WebSocket — Vercel tego nie wspiera.

## Struktura pliku

| Element | Opis |
|---|---|
| Warstwy ściany | Edytowalna tabela — mur, tynki, inne warstwy z grubością i lambdą |
| Materiał docieplenia | Wybór z listy (EPS, grafit, wełna, XPS, PIR) lub ręczne lambda |
| HDD (stopniodni) | Domyślnie 3500 K·dzień/rok (typowe dla Polski centralnej) |
| Taryfa gazu | MyOrlen W-3.6/W-3.9 + dystrybucja PSG (poznański, tarnowski, warszawski, wrocławski) |
| Sprawność kotła | Domyślnie 0.92 |

## Wzory

- **R warstwy** = grubość [m] / λ [W/(m·K)]
- **U** = 1 / (Rsi + ΣR + Rse)
- **Q roczne** = U × A × HDD × 24 / 1000 [kWh/rok]
- **Moc strat** = U × A × ΔT [W]
- **Koszt gazu** = (Q / η) × stawki zmienne + koszty stałe × 12, wszystko × (1 + VAT)

## Licencja

MIT
