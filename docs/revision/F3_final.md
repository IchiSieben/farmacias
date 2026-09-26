# F3 — revisión final del matcher v2

> Corrida autónoma del 2026-09-26. Rama `v2/f3-matcher`. Corrida de referencia:
> `2026-09-26T07-00-07Z` (la diaria de las 02:00), reprocesada `--desde-cache` sin red
> tras bajarle QuickView y fotos (`--completar`, 164 requests). Reproceso determinista:
> dos pasadas dan un `data.json` byte a byte igual.

## 1. Qué se aplicó (decisiones de iC7)

| Decisión | Cómo quedó | Dónde |
|---|---|---|
| Una fila = mismo producto registrado | sin cambio de definición; se refuerza con las reglas de abajo | `docs/MATCHING.md` §1 |
| Laboratorio distinto ⇒ no casa | lista de laboratorios conocidos con alias (Genfar y la línea de consumo de Boehringer → Sanofi; GSK/Glaxo/Haleon); se compara solo si **ambos** lados resuelven a uno. Siglas de Universal (FI, GF, PT, LG, IQ, MF). Boticas no trae laboratorio: se deduce por su R.S. con un mapa R.S.→laboratorio armado con Universal e InRetail en la misma corrida | `core/matcher.py` `_laboratorio_distinto`, `pipeline/build_snapshot.py` `laboratorios_por_rs` |
| Uno a uno greedy | filas InRetail del mismo producto (mismo R.S. o EAN + misma presentación y cantidad) se agrupan; todos los pares (grupo, SKU) se ordenan por fuerza de evidencia (curado > id/EAN > R.S. > texto/foto > zona gris) y luego score; se acepta saltando SKUs tomados. Sin húngaro | `build_snapshot._asignar` |
| Tapsin Día ↔ Noche | `dia`/`noche` como modificadores de fórmula, comparados **antes** del R.S. (Boticas muestra el mismo R.S. en ambas) | `_variante_distinta` |
| Huggies Puro y Natural ↔ Recién Nacido | etapa: "recién nacido" en un solo lado ya separa; tallas solo si ambos lados declaran una. También antes del R.S. (un R.S. cubre todas las tallas de un pañal) | `_etapa_distinta` |
| Tapsin Flu sobre ↔ blíster | tipo de envase desde el sufijo del SKU de Boticas (`-BLISTER`, `-SOBRE`) y la primera palabra de la presentación InRetail; solo el choque sobre/blíster | `_envase_distinto` |
| Cetirizina Portugal ↔ Universal FI | laboratorio distinto; la de Boticas también cae (su R.S. EN-01402 es el de la FI) | ver arriba |
| Ensure ↔ Ensure Advance | `advance` como modificador de fórmula | `_MODIFICADOR_NUCLEO` |
| Imagen solo confirma | sin cambio (`VETO_IMAGEN = False`) | — |
| Equivalentes no se muestran | sin cambio en datos; F4 no los pinta | — |

Reglas añadidas por la revisión de esta corrida (mismo criterio, casos que aparecieron al
aplicar el uno a uno):

- **Zona gris exige la marca.** Con texto < 85, la marca de la referencia (si no es un
  laboratorio y aparece en su propio nombre) tiene que estar en el nombre o la URL del
  candidato. Sin esto, una fila que pierde su mejor SKU caía al siguiente: "Huggies Puro y
  Natural" → toallitas Agugu; Eucerin Oil Control → Anthelios de La Roche-Posay.
- **`flex` y `triplesure` como modificadores**: Supracalm Flex (otro activo) ≠ Supracalm 1 g;
  Pediasure Triplesure ≠ Pediasure (como ya estaba Peptigro).
- **Vetos curados** (`tests/matches_curados.yaml`): toallitas Huggies Puro y Natural contra
  las líneas 4 en 1, Cuidados 4 en 1 y Triple Acción; Pediasure (EAN de Peptigro) contra
  Pediasure 10+ de Boticas. La línea de una toallita es texto libre: no hay regla razonable.

Regresión: **85/85** (66 previos + 17 de esta revisión + 2 de asignación uno a uno), en
Python 3.12 y 3.9. Cada caso malo va por la ruta que lo cruzó (mismo R.S., foto idéntica,
atributos de laboratorio) y tiene su gemelo que debe seguir casando. Suites `http_cache`,
`credencial`, `publish`, `sincronizar`: OK.

## 2. Cifras, misma corrida (`2026-09-26T07-00-07Z`)

| | main | F3 antes de hoy | **F3 final** |
|---|---|---|---|
| Filas | 294 | 295 | **295** |
| Con Boticas | 109 | 97 | **87** |
| Con Universal | 77 | 74 | **71** |
| Con las 4 cadenas | 54 | 50 | **42** |
| SKUs cruzados a más de una fila | **17** | 9 | **0** |
| Equivalentes guardados (no se muestran) | — | — | 19 |
| Cruces en zona gris (`revisar`) | — | — | 10 |

Menos cobertura a propósito: un "—" es mejor que un falso positivo. Métodos en F3 final:
Universal EAN 51, R.S. 19 (Boticas 15 + Universal 4), texto 79, foto 3, curado 6.

## 3. Cambios de cruce vs main (misma corrida)

32 cruces quitados, 4 agregados, 5 cambiados de SKU. Por motivo:

- **Revisión de hoy (decisiones iC7):** Tapsin Plus Día (→ SKU Noche), Tapsin Flu Día
  (→ `49718-BLISTER`), Tapsin Plus Caliente Noche fracción (SKU que ya tenía otra fila),
  Huggies Puro y Natural (Boticas y Universal), Ensure (→ Advance), Cetirizina Portugal
  (→ Universal FI; Boticas cambia a un SKU de S/ 3,00 alineado con Portugal), Diclofenaco
  1 % Portugal (→ Universal FI), Eucerin (→ Anthelios), Pediasure ×2, Supracalm fracción
  (SKU Flex fuera; el blíster lo toma la otra fila Supracalm).
- **Laboratorio por R.S.:** Omeprazol Portugal S/ 12 ↔ Boticas S/ 24,2 (R.S. de otro
  laboratorio) → queda como equivalente. Diclofenaco 268175 pierde Boticas 12755 (ver §5).
- **Uno a uno:** Paracetamol 500 (dos filas InRetail sin R.S. querían el mismo SKU),
  Aspirador Owawa/Nuby (cada fila se queda con su marca), Clorfenamina, Paracetamol 120
  jarabe.
- **Ya decididos en la sesión F3 anterior (R.S. distinto → equivalente):** Naproxeno 550
  (3), Paracetamol 120 solución, Hioscina, Magnesio Vivactiv ×2, Sunvit ×2, Bisolvon Niños,
  CeraVe aceite, Panadol efervescente fracción.
- **Agregados:** Calcibone D3 (Universal, R.S.), Redoxon Total (Boticas, R.S.), Centrum
  Silver (Boticas, foto idéntica), Paracetamol 500 108177 (Boticas; antes lo tenía otra fila).

## 4. Muestra de 30 cruces (15 Boticas + 15 Universal, semilla 20260926)

⚠ = zona gris (texto 70–85): casa, pero va marcado para revisar.

| # | Fila Inkafarma | S/ Inka | Cadena | S/ | Método | Enlaces |
|---|---|---|---|---|---|---|
| 1 | Apronax 550mg Tableta Recubierta (CAJA 120 UN) | 216.00 | Boticas | 228.00 | registro_sanitario 100 | [Inka](https://inkafarma.pe/producto/apronax-550mg-tabletas-recubiertas/230451) · [Boticas](https://www.boticasperu.pe/botica_en_casa/antiinflamatorios/apronax_550mg_tableta_recubierta_-_caja_120_un/12313-CAJA.html) |
| 2 | Bicerto 150mg Comprimido de Liberación prolongada (CAJA 10 UN) | 31.00 | Boticas | 31.20 | fuzzy 94 | [Inka](https://inkafarma.pe/producto/bicerto-150mg-comprimido-de-liberacion-prolongada/033626) · [Boticas](https://www.boticasperu.pe/tratamiento/bicerto_150mg__-_caja_10_comprimidos/38468.html) |
| 3 | Bonadol Cápsulas Blandas (CAJA 100 UN) | 100.00 | Boticas | 98.00 | fuzzy 100 | [Inka](https://inkafarma.pe/producto/bonadol-capsulas-blandas/068522) · [Boticas](https://www.boticasperu.pe/botica_en_casa/resfrio/dolor/bonadol_capsulas_blandas_500_g_-_caja_100_un/46770-CAJA.html) |
| 4 | Centrum Silver Comprimido Recubierto (FRASCO 30 UN) | 47.60 | Boticas | 47.50 | imagen 85 | [Inka](https://inkafarma.pe/producto/centrum-silver-comprimido-recubierto/072373) · [Boticas](https://www.boticasperu.pe/nutricion/vitaminas_y_minerales/suplemento_nutricional_centrum_silver_-_frasco_30_un/46930.html) |
| 5 | Desloratadina 5mg Tabletas recubiertas (CAJA 100 UN) | 20.00 | Boticas | 27.90 | fuzzy 93 | [Inka](https://inkafarma.pe/producto/desloratadina-5mg-tabletas-recubiertas/017199) · [Boticas](https://www.boticasperu.pe/botica_en_casa/antihistaminicos/desloratadina_5mg_tableta_recubierta_-_caja_100_un/42683.html) |
| 6 | Fastum 2.5% Gel (TUBO 30 GR) | 19.60 | Boticas | 20.00 | fuzzy 93 | [Inka](https://inkafarma.pe/producto/fastum-2-5-gel/425793) · [Boticas](https://www.boticasperu.pe/tratamiento/osteoarticulares/fastum_gel_-_tubo_30_g/14390.html) |
| 7 | Gel Limpiador La Roche-Posay Effaclar (FRASCO 400 ML) | 142.90 | Boticas | 142.90 | fuzzy 100 | [Inka](https://inkafarma.pe/producto/effaclar-gel-limpiador-facial-400ml-la-roche-posay/009309) · [Boticas](https://www.boticasperu.pe/dermocosmetica/faciales/antimanchas/gel_limpiador_la_roche_posay_effaclar_micro-exfoliante_-_frasco_400_ml/50274.html) |
| 8 | Glucerna Sabor Vainilla (LATA 850 GR) | 139.90 | Boticas | 139.90 | fuzzy 100 | [Inka](https://inkafarma.pe/producto/glucerna-sabor-vainilla/068478) · [Boticas](https://www.boticasperu.pe/adulto_mayor/formulas_adultos/glucerna/glucerna_sabor_vainilla_-_lata_850_g/43729.html) |
| 9 | Loratadina 5Mg/5Ml Jarabe (FRASCO 60 ML) | 3.40 | Boticas | 3.40 | fuzzy 93 | [Inka](https://inkafarma.pe/producto/loratadina-5mg-5ml-jarabe/420618) · [Boticas](https://www.boticasperu.pe/botica_en_casa/alergias/loratadina_5_mg_jarabe_-_frasco_60_ml/01110.html) |
| 10 | Miodel Relax NF 450mg+35mg Tableta Recubierta (CAJA 30 UN) | 44.00 | Boticas | 48.00 | fuzzy 93 | [Inka](https://inkafarma.pe/producto/miodel-relax-500mg-50mg-75mg-tab/038169) · [Boticas](https://www.boticasperu.pe/botica_en_casa/analgesicos/medicamentos/miodel_relax_nf_tabletas_-_caja_30_un/38481-CAJA.html) |
| 11 | Mucosolvan Compositum 15mg - 0.01 mg/5ml Jarabe (FRASCO 120 ML) | 24.90 | Boticas | 24.90 | fuzzy 89 | [Inka](https://inkafarma.pe/producto/mucosolvan-compositum-adultos-jarabe/426469) · [Boticas](https://www.boticasperu.pe/botica_en_casa/resfrio/tos_y_dolor_de_garganta/mucosolvan_compositum_adulto_-_frasco_120_ml/00464.html) |
| 12 | Naproxeno Sódico 550 Mg Tableta Recubierta (BLÍSTER 10 UN) | 3.80 | Boticas | 3.80 | fuzzy 92 | [Inka](https://inkafarma.pe/producto/naproxeno-sodico-550mg-tableta-recubierta/203068) · [Boticas](https://www.boticasperu.pe/tratamiento/analgesicos_y_antiflamatorios/naproxeno_550_mg_tabletas_-_blister_10_un/12318-BLISTER.html) |
| 13 | Panadol 500mg Tableta Efervescente (CAJA 24 UN) | 24.00 | Boticas | 27.20 | registro_sanitario 100 | [Inka](https://inkafarma.pe/producto/panadol-efervescente-500-mg-tabletas/108234) · [Boticas](https://www.boticasperu.pe/botica_en_casa/resfrio/fiebre_y_congestion_nasal-1/panadol_500_mg_tableta_efervescente_-_caja_24_un/15063-CAJA.html) |
| 14 | Protector Solar La Roche Posay Anthelios UVMune 400 Oil Control Fluido Invisible FPS 50+ (TUBO 50 ML) | 125.90 | Boticas | 125.90 | fuzzy 91 | [Inka](https://inkafarma.pe/producto/protector-solar-la-roche-posay-anthelios-uvmune400/068513) · [Boticas](https://www.boticasperu.pe/dermocosmetica/faciales/piel_grasa/fotoprotector/protector_solar_anthelios_uv_mune_400_oil_control_fluido_fps_50_-_frasco_50_ml/45615.html) |
| 15 | Érgico 2.5mg/5ml Suspensión oral (FRASCO 60 ML) | 26.40 | Boticas | 26.40 | fuzzy 93 | [Inka](https://inkafarma.pe/producto/ergico-2-5-mg-5-ml-solucion-oral/023780) · [Boticas](https://www.boticasperu.pe/botica_en_casa/alergias/ergico_2.5mg%2F5ml_solucion_oral_-_frasco_60_ml/34922.html) |
| 16 | Ambroxol 30mg/5ml Jarabe (FRASCO 120 ML) | 2.90 | Universal | 3.49 | ean 100 | [Inka](https://inkafarma.pe/producto/ambroxol-30-mg-5-ml-jarabe/300091) · [Universal](https://www.farmaciauniversal.com/ambroxol-30-mg-5-ml-pt-solucion-oral-frasco-120-ml/p) |
| 17 | Aspirador Nasal Owawa (BLÍSTER 1 UN) | 34.90 | Universal | 34.90 | ean 100 | [Inka](https://inkafarma.pe/producto/aspirador-nasal-owawa-1un/006333) · [Universal](https://www.farmaciauniversal.com/owawa-aspirador-nasal-blister-1-und/p) |
| 18 | Bisolvon 8mg/5ml Jarabe Adultos - Frasco 120 ML (FRASCO 120 ML) | 21.10 | Universal | 23.27 | ean 100 | [Inka](https://inkafarma.pe/producto/bisolvon-8mg-5ml-jarabe-adultos/420207) · [Universal](https://www.farmaciauniversal.com/bisolvon-adultos-8-mg5-ml-jarabe-frasco-120-ml/p) |
| 19 | Centrum Comprimido Recubierto (FRASCO 30 UN) | 41.40 | Universal | 41.40 | ean 100 | [Inka](https://inkafarma.pe/producto/centrum-comprimido-recubierto/072372) · [Universal](https://www.farmaciauniversal.com/centrum-adulto-comprimidos-recubiertos-frasco-30-und/p) |
| 20 | Citrato de Calcio con Vitamina D3 Mason Tabletas (FRASCO 60 UN) | 80.00 | Universal | 76.90 | ean 100 | [Inka](https://inkafarma.pe/producto/calcium-citrate-with-vitamin-d3-tabletas/406835) · [Universal](https://www.farmaciauniversal.com/mason-citrato-de-calcio-vitamina-d3-comprimidos-frasco-60-und/p) |
| 21 | Desloratadina 2.5mg/5ml Jarabe Genfar - Frasco 60 ML (FRASCO 60 ML) | 20.10 | Universal | 22.40 | ean 100 | [Inka](https://inkafarma.pe/producto/desloratadina-2-5mg-5ml-jarabe-genfar/428332) · [Universal](https://www.farmaciauniversal.com/desloratadina-25-mg-5-ml-gf-jarabe-frasco-60-ml/p) |
| 22 | Fotoprotector Isdin FusionWater Magic Repair SPF50 (FRASCO 50 ML) | 139.90 | Universal | 99.91 | fuzzy 88 | [Inka](https://inkafarma.pe/producto/fotoprotector-isdin-fusion-water-magic-repair/077779) · [Universal](https://www.farmaciauniversal.com/isdin-fotoprotector-fusion-water-magic-spf50-frasco-50-ml/p) |
| 23 | Glucerna Triple Care Líquido Sabor Vainilla (FRASCO 220 ML) | 12.90 | Universal | 12.90 | fuzzy 80 ⚠ | [Inka](https://inkafarma.pe/producto/glucerna-triple-care-liquido-vainilla-220ml/085152) · [Universal](https://www.farmaciauniversal.com/glucerna-bebible-sabor-vainilla-frasco-220-ml/p) |
| 24 | Grifantil NF Suspensión Oral (FRASCO 60 ML) | 25.50 | Universal | 32.15 | fuzzy 100 | [Inka](https://inkafarma.pe/producto/grifantil-nf-suspension-oral/079478) · [Universal](https://www.farmaciauniversal.com/grifantil-nf-suspension-oral-frasco-60-ml/p) |
| 25 | Gripacheck Cápsula Blanda (BLÍSTER 4 UN) | 7.20 | Universal | 7.20 | ean 100 | [Inka](https://inkafarma.pe/producto/gripacheck-capsula-blanda/026014) · [Universal](https://www.farmaciauniversal.com/gripacheck-capsulas-blandas-blister-4-und/p) |
| 26 | Panadol Pediátrico 100mg/ml Solución Oral (FRASCO 15 ML) | 15.80 | Universal | 20.00 | ean 100 | [Inka](https://inkafarma.pe/producto/panadol-pediatrico-100mg-ml-solucion-oral-gotas/108220) · [Universal](https://www.farmaciauniversal.com/panadol-ninos-100mgml-gotas-frasco-15-ml/p) |
| 27 | Paracetamol 160mg/5mL Jarabe (FRASCO 90 ML) | 7.80 | Universal | 7.30 | ean 100 | [Inka](https://inkafarma.pe/producto/paracetamol-160mg-5ml-jarabe/035461) · [Universal](https://www.farmaciauniversal.com/paracetamol-160-mg-5-ml-gf-jarabe-sabor-fresa-frasco-90-ml/p) |
| 28 | Pañales Huggies G Bigpack Natural Care (BOLSA 66 UN) | 65.50 | Universal | 65.50 | ean 100 | [Inka](https://inkafarma.pe/producto/panales-huggies-g-bigpack-natural-care-bolsa-66-un/036335) · [Universal](https://www.farmaciauniversal.com/huggies-natural-care-panales-para-bebe-talla-g-bolsa-66-und/p) |
| 29 | Sal De Andrews Polvo Efervescente Triple (UNIDAD 1 UN) | 1.10 | Universal | 1.32 | ean 100 | [Inka](https://inkafarma.pe/producto/sal-de-andrews-polvo-efervescente-triple-accion/003407) · [Universal](https://www.farmaciauniversal.com/sal-andrews-triple-accion-polvo-efervescente-sobre-1-und/p) |
| 30 | Supracalm flex 300mg+250mg Comprimido (BLÍSTER 10 UN) | 21.20 | Universal | 25.00 | ean 100 | [Inka](https://inkafarma.pe/producto/supracalm-flex-300mg-250mg-comprimido/037469) · [Universal](https://www.farmaciauniversal.com/supracalm-flex-300-mg-250-mg-comprimidos-blister-10-und/p) |
Revisada a mano: 28 correctos; #5 dudoso (ver §5.1); #23 dudoso (§5.4).

## 5. Casos que siguen dudosos (no se tocaron: sin regla razonable ni certeza)

1. **Desloratadina 5 mg Labogen (017199, S/ 20) ↔ Boticas 42683 (S/ 27,90).** El R.S. de
   ese SKU (EN-08918) es el de la Desloratadina Portugal en la corrida del 25-09, pero el
   26-09 la fila Portugal no salió en la búsqueda de Inkafarma y el mapa R.S.→laboratorio
   de la corrida no lo conoce. Propuesta: un mapa persistente R.S.→laboratorio entre
   corridas (`config/laboratorios_rs.yaml`, se alimenta solo).
2. **Diclofenaco 1 % gel 268175:** InRetail dice marca PORTUGAL pero su EAN es el de la FI
   de Universal. El veto por laboratorio usa la marca de InRetail y deja fuera el Boticas
   12755 (R.S. de la FI), que probablemente sí es el mismo producto. Queda en "—".
3. **Pediasure Sabor Vainilla (074030/074032):** InRetail trae el EAN de Pediasure Peptigro;
   el nombre no lo dice. Universal cruza por EAN con Peptigro. Si Inka vende Peptigro bajo
   ese nombre, está bien; si no, el EAN de InRetail está mal cargado.
4. **Glucerna Triple Care líquido 220 ml ↔ Universal "Glucerna Bebible" 220 ml** (zona gris 80).
5. **Cosmética en zona gris:** Eucerin Hyaluron-Filler Reafirmante ↔ Universal "Epigenetic
   Serum" (84); La Roche-Posay Anthelios UVMune 400 ↔ Universal "Antimanchas" (75). Misma
   gama, variante probablemente distinta.
6. **Tapsin Plus Antigripal Día:** el SKU correcto de Boticas (45619-CAJA) queda como
   *equivalente*: su QuickView muestra otro R.S. que Inkafarma. Parece un R.S. cruzado en
   Boticas (la de Noche muestra el de Día). No se curó un match sin verificación humana.
7. **Supracalm 1 g:** dos filas InRetail (caja 10 y blíster 10, sin R.S.) compiten por dos
   SKUs de Boticas (caja 10 y blíster 10); el reparto puede salir cruzado. Mismo producto
   y cantidad: no es falso positivo, solo el envase.
