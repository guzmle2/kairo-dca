# Notas del perfil de Estados Unidos (US)

Estado: **borrador**. Divisa USD. Ajustes en `config/perfil_us.json`; aquí solo las notas de referencia (fiscalidad, protección, riesgos y fuentes), que no forman parte de la tesis.

## Nota perfil

Borrador sin verificar del todo: el sistema no lo usa hasta que pase a activo. Un residente en EE. UU. no debe comprar el UCITS irlandés (régimen de fondos extranjeros, PFIC); no hay ETF de acumulación en EE. UU. y los dividendos tributan cada año. Fuentes en el plan (F5-08).

## Isin nota

en este perfil la lista usa tickers de EE. UU. porque el ISIN oficial de VT y VTI está pendiente de verificar

## Nota fiscal

Retiene el contribuyente (1099-DIV, 1099-B, Form 8949, Schedule D). Ganancias a largo plazo 2026 (IRS Rev. Proc. 2025-32): 0 % hasta 49.450 USD de renta imponible (individual), 98.900 (conjunta), 66.200 (cabeza de familia); 15 % hasta 545.500 / 613.700 / 579.600; 20 % por encima. Vender antes de un año tributa como renta ordinaria. Impuesto adicional del 3,8 % (NIIT) con renta por encima de 200.000 USD (individual), 250.000 (conjunta). Wash sale: no se deduce la pérdida si se recompra lo sustancialmente idéntico 30 días antes o después, también dentro de una IRA. Crédito fiscal extranjero sin formulario 1116 si el impuesto no supera 300 USD (600 conjunta). 401(k) 24.500 USD (más 8.000 con 50 años o más); IRA y Roth IRA 7.500 USD combinados (más 1.100 con 50 años o más); Roth se reduce entre 153.000 y 168.000 USD (individual). SIPC 500.000 USD (250.000 de efectivo)

## Productos candidatos

- VT (Vanguard Total World Stock, TER 0,06 %)
- VTI (Vanguard Total Stock Market, TER 0,03 %)

## Advertencias

- un fondo europeo (UCITS) es PFIC para un residente en EE. UU.: no comprar IE00B4L5Y983; la exención de presentar el Form 8621 solo existe por debajo de 25.000 USD (50.000 en conjunta) y no elimina el régimen
- Trade Republic no abre cuenta a personas de EE. UU. (FATCA); Fidelity y Schwab restringen servicios a expatriados (prensa)
- no hay ETF de acumulación en EE. UU.: los dividendos tributan cada año

## Fuentes

- https://www.irs.gov/pub/irs-drop/rp-25-32.pdf
- https://www.irs.gov/taxtopics/tc409
- https://www.irs.gov/taxtopics/tc559
- https://www.irs.gov/publications/p550
- https://www.irs.gov/publications/p514
- https://www.irs.gov/newsroom/401k-limit-increases-to-24500-for-2026-ira-limit-increases-to-7500
- https://www.irs.gov/instructions/i8621
- https://www.fidelity.com/trading/recurring-investments
- https://investor.vanguard.com/investment-products/etfs/profile/vt

## Pendiente de verificar

- ISIN oficial de VT (US9220427424) y VTI (US9229087690): solo constan en la bolsa mexicana
- tipos de los dividendos cualificados en la Pub 550
- impuesto estatal
- compras recurrentes de ETF en Schwab (en Fidelity sí, desde 1 USD)
- crédito fiscal extranjero que traspasa VT
- regla general de aprovechar primero la aportación del empleador al 401(k)
