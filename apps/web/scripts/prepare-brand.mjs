// Gera o símbolo do ALN Hub ia a partir da matriz transparente da ALN Digital (a mesma marca usada no ALN Hub).
// Uso: node scripts/prepare-brand.mjs "D:/projetos_aln/images/alndigital/logos/alndigital_parafundoescuro.png"
// Regras do ecossistema: recorta o transparente uma vez, reduz uma vez com Lanczos, nunca usa paleta de 256 cores.
import { mkdir } from "node:fs/promises";
import sharp from "sharp";

const source = process.argv[2];
if (!source) {
  console.error("Informe o caminho da matriz PNG transparente.");
  process.exit(1);
}
const out = new URL("../public/brand/", import.meta.url);
await mkdir(out, { recursive: true });
const file = name => new URL(name, out).pathname.replace(/^\/([A-Za-z]:)/, "$1");

const trimmed = await sharp(source).trim({ threshold: 1 }).png().toBuffer();
const { width: tw, height: th } = await sharp(trimmed).metadata();
console.log(`matriz recortada: ${tw}x${th}`);

/** The logo centered in a transparent square, like the ALN Hub mark (logo fills ~84% of the width). */
async function markSquare(size, fill = 0.84) {
  const w = Math.round(size * fill);
  const logo = await sharp(trimmed).resize({ width: w, kernel: "lanczos3" }).png().toBuffer();
  const { height } = await sharp(logo).metadata();
  return sharp({ create: { width: size, height: size, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } } })
    .composite([{ input: logo, left: Math.round((size - w) / 2), top: Math.round((size - height) / 2) }]);
}

const gradient = size => Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7655f6"/><stop offset="1" stop-color="#dafa73"/></linearGradient></defs>
  <rect width="${size}" height="${size}" rx="${Math.round(size * 0.3)}" fill="url(#g)"/></svg>`);

const plate = (size, bg) => Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}">
  <rect width="${size}" height="${size}" fill="${bg}"/></svg>`);

// Header/footer mark (the gradient box is CSS; this is the transparent logo inside it).
for (const size of [72, 108, 144]) {
  await (await markSquare(size)).webp({ quality: 92, alphaQuality: 100 }).toFile(file(`aln-mark-${size}.webp`));
}

// App icons: same composition as the ALN Hub mark (gradient box + logo).
async function icon(size, name, { rounded = true, fill = 0.8 } = {}) {
  const logo = await (await markSquare(size, fill)).png().toBuffer();
  const base = rounded ? gradient(size) : Buffer.from(gradient(size).toString().replace(/rx="\d+"/, 'rx="0"'));
  await sharp(base).composite([{ input: logo }]).png({ compressionLevel: 9 }).toFile(file(name));
}
await icon(32, "favicon-32.png");
await icon(64, "favicon-64.png");
await icon(180, "apple-touch-icon.png", { rounded: false });
await icon(192, "icon-192.png");
await icon(512, "icon-512.png");
// Maskable: full-bleed background, logo inside the 80% safe zone.
await icon(512, "icon-maskable-512.png", { rounded: false, fill: 0.62 });
// Social and JSON-LD: logo on the site background.
const onDark = await (await markSquare(600, 0.86)).png().toBuffer();
await sharp(plate(600, "#07070c")).composite([{ input: onDark }]).png().toFile(file("aln-logo-600.png"));
console.log("pronto: public/brand/");
