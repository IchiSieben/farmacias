// Texto largo de /metodologia (brief §5.4). Vive aquí y no en es.json/en.json porque
// son secciones con párrafos y listas; las dos versiones deben tener las mismas
// secciones en el mismo orden (se verifica al importar: el build falla si no).
import type { Idioma } from './index';

export interface Seccion {
  id: string;
  titulo: string;
  parrafos: string[];
  lista?: string[];
}

const es: Seccion[] = [
  {
    id: 'grupos',
    titulo: 'Las cuatro cadenas y sus grupos',
    parrafos: [
      'Inkafarma y Mifarma pertenecen al mismo grupo, InRetail (Intercorp), y comparten catálogo: un producto tiene el mismo código en las dos. Por eso ese cruce es exacto y la comparación entre ellas muestra cómo un mismo grupo pone precios distintos a sus dos marcas.',
      'Boticas Perú y Farmacia Universal son cadenas independientes, con catálogos propios. Con ellas hay que encontrar el mismo artículo producto por producto, y por eso aparecen en menos filas.',
    ],
  },
  {
    id: 'captura',
    titulo: 'Cómo se capturan los precios',
    parrafos: [
      'Una vez al día (02:00, hora de Lima) un proceso consulta el catálogo público de cada tienda: el mismo buscador que usa su web. No inicia sesión, no usa carrito ni checkout y espera de 2 a 6 segundos entre consultas a una misma tienda.',
      'La respuesta cruda se guarda antes de procesarla, así cada captura se puede volver a procesar sin volver a consultar las tiendas. Cada captura queda fechada; subidas, bajadas y promociones salen de comparar una captura con la anterior.',
      'El precio es el publicado en la web ese día. Descuentos con tarjeta, de tienda física o por cantidad pueden no estar reflejados.',
    ],
  },
  {
    id: 'emparejado',
    titulo: 'Cómo se decide que es el mismo producto',
    parrafos: [
      'La referencia es el catálogo de Inkafarma: cada fila es un producto en una presentación concreta (caja, blíster, frasco). Para Boticas Perú y Farmacia Universal se buscan candidatos y cada uno pasa por estas capas, en orden:',
    ],
    lista: [
      'Código de barras (EAN) cuando la tienda lo publica: si coincide, es el mismo producto.',
      'Guardas previas: etapa o talla (recién nacido frente a talla G), variante de fórmula (Día frente a Noche, Advance, Flex) y tipo de envase (sobre frente a blíster). Si chocan, se descarta aunque el resto coincida.',
      'Registro sanitario: si los dos lados lo muestran, el mismo registro confirma y uno distinto descarta.',
      'Reglas duras: la misma cantidad exacta del envase, sin choques de concentración, forma farmacéutica, principio activo ni laboratorio, y un precio dentro de 3× del de Inkafarma.',
      'Parecido del nombre: desde 85 sobre 100 se acepta; entre 70 y 85 solo si la marca coincide, y la fila queda marcada para revisión.',
      'Foto: una foto casi idéntica puede confirmar un cruce, pero nunca lo descarta (las tiendas reutilizan fotos).',
      'Uno a uno: cada artículo de una tienda se asigna a una sola fila, empezando por la evidencia más fuerte (código, registro sanitario, nombre).',
    ],
  },
  {
    id: 'criterio',
    titulo: 'El criterio: mejor un “—” que un cruce falso',
    parrafos: [
      'Juntar dos productos distintos en una fila inventa un ahorro que no existe. Por eso, ante la duda, el comparador deja la casilla vacía. Una fila “a revisar” (la más cara cuesta más de 3 veces la más barata) sale al final del orden por ahorro y con un aviso, porque casi siempre delata un cruce equivocado.',
      'Los cruces del emparejador se prueban contra una lista de pares revisados a mano, buenos y malos, antes de cada cambio.',
    ],
  },
  {
    id: 'alcance',
    titulo: 'Qué cubre y qué no',
    parrafos: [
      'Cubre medicamentos de venta libre, antigripales, antialérgicos, digestivos, vitaminas y suplementos, nutrición, dermocosmética y productos de bebé: alrededor de 300 filas elegidas por categoría, no el catálogo completo de cada cadena.',
      'La cosmética y el cuidado personal (desodorantes, jabones, champús) no se comparan entre grupos. El emparejador se apoya en el principio activo y la concentración, y aquí no existen: la misma marca vende modelos casi iguales con nombres parecidos. En esa categoría solo se comparan Inkafarma y Mifarma, que comparten el código del producto.',
    ],
  },
  {
    id: 'numeros',
    titulo: 'Qué significa cada número',
    parrafos: [],
    lista: [
      'Ahorro: la diferencia entre el precio más alto y el más bajo del mismo producto, entre las cadenas que tienes activas.',
      'Brecha (en Panorama): cuánto más cuesta un producto en una cadena que en la más barata.',
      '▲ ▼: el precio subió o bajó frente a la captura anterior.',
      'Nuevo: la fila no estaba en la captura anterior.',
    ],
  },
  {
    id: 'aviso',
    titulo: 'Aviso y licencia',
    parrafos: [
      'Proyecto independiente, sin afiliación con Inkafarma, Mifarma, Boticas Perú, Farmacia Universal ni sus grupos. Sus nombres y logos pertenecen a sus dueños y se usan solo para identificar cada tienda. Los precios son públicos, pueden cambiar y deben confirmarse en cada tienda antes de comprar. Esto no es consejo médico.',
      'El código es abierto, con licencia Apache 2.0.',
    ],
  },
];

const en: Seccion[] = [
  {
    id: 'grupos',
    titulo: 'The four chains and their groups',
    parrafos: [
      'Inkafarma and Mifarma belong to the same group, InRetail (Intercorp), and share a catalogue: a product has the same code in both. That match is therefore exact, and comparing them shows how one group prices its two brands differently.',
      'Boticas Perú and Farmacia Universal are independent chains with their own catalogues. The same item has to be found product by product, which is why they appear in fewer rows.',
    ],
  },
  {
    id: 'captura',
    titulo: 'How prices are captured',
    parrafos: [
      'Once a day (02:00, Lima time) a process queries each store’s public catalogue: the same search its website uses. It never logs in, never uses the cart or checkout, and waits 2 to 6 seconds between queries to the same store.',
      'The raw response is stored before it is processed, so every capture can be reprocessed without querying the stores again. Each capture is dated; price rises, drops and promotions come from comparing a capture with the previous one.',
      'The price is the one published on the website that day. Card, in-store or volume discounts may not be reflected.',
    ],
  },
  {
    id: 'emparejado',
    titulo: 'How we decide it is the same product',
    parrafos: [
      'The reference is Inkafarma’s catalogue: each row is a product in one specific presentation (box, blister, bottle). For Boticas Perú and Farmacia Universal, candidates are searched and each goes through these layers, in order:',
    ],
    lista: [
      'Barcode (EAN) when the store publishes it: if it matches, it is the same product.',
      'Early guards: stage or size (newborn versus size L), formula variant (Day versus Night, Advance, Flex) and pack type (sachet versus blister). A clash rules the candidate out even if everything else matches.',
      'Sanitary registration: when both sides show it, the same number confirms and a different one rules out.',
      'Hard rules: the exact same pack size, no clash in strength, dosage form, active ingredient or manufacturer, and a price within 3× of Inkafarma’s.',
      'Name similarity: 85 out of 100 or more is accepted; between 70 and 85 only if the brand matches, and the row is flagged for review.',
      'Photo: a near-identical photo can confirm a match but never rules one out (stores reuse photos).',
      'One to one: each store item is assigned to a single row, starting with the strongest evidence (code, sanitary registration, name).',
    ],
  },
  {
    id: 'criterio',
    titulo: 'The rule: a “—” beats a false match',
    parrafos: [
      'Putting two different products in one row invents a saving that does not exist. So, when in doubt, the comparison leaves the cell empty. A row “to review” (the most expensive price is more than 3 times the cheapest) goes to the end of the savings order with a warning, because it almost always reveals a wrong match.',
      'The matcher is tested against a list of hand-checked pairs, good and bad, before every change.',
    ],
  },
  {
    id: 'alcance',
    titulo: 'What it covers and what it does not',
    parrafos: [
      'It covers over-the-counter medicines, cold and flu, allergy, digestive, vitamins and supplements, nutrition, dermocosmetics and baby products: around 300 rows chosen by category, not each chain’s full catalogue.',
      'Cosmetics and personal care (deodorants, soaps, shampoos) are not compared across groups. The matcher relies on the active ingredient and strength, and here there are none: the same brand sells near-identical models with similar names. In that category only Inkafarma and Mifarma are compared, since they share the product code.',
    ],
  },
  {
    id: 'numeros',
    titulo: 'What each number means',
    parrafos: [],
    lista: [
      'Saving: the difference between the highest and the lowest price of the same product, across the chains you have switched on.',
      'Gap (in Overview): how much more a product costs in a chain than in the cheapest one.',
      '▲ ▼: the price went up or down since the previous capture.',
      'New: the row was not in the previous capture.',
    ],
  },
  {
    id: 'aviso',
    titulo: 'Notice and licence',
    parrafos: [
      'Independent project, not affiliated with Inkafarma, Mifarma, Boticas Perú, Farmacia Universal or their groups. Their names and logos belong to their owners and are used only to identify each store. Prices are public, may change and should be checked in each store before buying. This is not medical advice.',
      'The code is open source, under the Apache 2.0 licence.',
    ],
  },
];

if (es.map((s) => s.id).join() !== en.map((s) => s.id).join()) {
  throw new Error('metodologia: las secciones ES y EN no coinciden');
}

export const METODOLOGIA: Record<Idioma, Seccion[]> = { es, en };
