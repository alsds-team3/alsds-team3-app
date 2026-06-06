// Business category -> NAICS code mapping
// Lets users type plain-language categories like "coffee shop" instead of digits.
const NAICS_MAP = {
  "supermarket": "4451",
  "grocery": "4451",
  "grocery store": "4451",
  "convenience store": "4452",
  "convenience": "4452",
  "gas station": "4471",
  "pharmacy": "4461",
  "drug store": "4461",
  "clothing": "4481",
  "clothing store": "4481",
  "apparel": "4481",
  "shoe store": "4482",
  "jewelry": "4483",
  "sporting goods": "4511",
  "book store": "4512",
  "bookstore": "4512",
  "department store": "4522",
  "electronics": "4431",
  "electronics store": "4431",
  "furniture": "4421",
  "furniture store": "4421",
  "home improvement": "4441",
  "hardware": "4441",
  "hardware store": "4441",
  "building materials": "4441",
  "florist": "4531",
  "office supplies": "4532",
  "pet store": "4539",
  "restaurant": "7225",
  "full service restaurant": "7225",
  "fast food": "7225",
  "coffee shop": "7225",
  "coffee": "7225",
  "cafe": "7225",
  "café": "7225",
  "bar": "7224",
  "pub": "7224",
  "bakery": "3118",
  "hotel": "7211",
  "motel": "7211",
  "gym": "7139",
  "fitness center": "7139",
  "salon": "8121",
  "hair salon": "8121",
  "barber": "8121",
  "barber shop": "8121",
  "dry cleaner": "8123",
  "laundry": "8123",
  "auto repair": "8111",
  "car wash": "8111",
  "bank": "5221",
  "movie theater": "5121",
  "cinema": "5121"
};

function resolveBusinessCategory(input) {
  if (!input) return null;
  const text = String(input).trim().toLowerCase();
  if (/^\d{2,6}$/.test(text)) return text;
  if (NAICS_MAP[text]) return NAICS_MAP[text];
  // try fuzzy: longest matching key contained in input
  let best = null;
  for (const key of Object.keys(NAICS_MAP)) {
    if (text.includes(key)) {
      if (!best || key.length > best.length) best = key;
    }
  }
  return best ? NAICS_MAP[best] : null;
}

window.NAICS_MAP = NAICS_MAP;
window.resolveBusinessCategory = resolveBusinessCategory;
