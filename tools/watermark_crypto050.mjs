// Offline publisher helper. Secrets arrive through stdin, never command arguments.
import { readFileSync } from 'node:fs';
import { generateKeyPairSync, createPrivateKey, createPublicKey, sign, verify,
  randomBytes, scryptSync, createCipheriv, createDecipheriv } from 'node:crypto';

const MAX = 4 * 1024 * 1024;
function bytes(value, limit = MAX) {
  if (typeof value !== 'string' || value.length > Math.ceil(limit / 3) * 4 ||
      !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)) throw new Error();
  const out = Buffer.from(value, 'base64');
  if (out.length > limit || out.toString('base64') !== value) throw new Error();
  return out;
}
function privateKey(value) {
  const key = createPrivateKey({ key: bytes(value, 256), format: 'der', type: 'pkcs8' });
  if (key.asymmetricKeyType !== 'ed25519') throw new Error();
  return key;
}
function publicKey(value) {
  const key = createPublicKey({ key: bytes(value, 128), format: 'der', type: 'spki' });
  if (key.asymmetricKeyType !== 'ed25519') throw new Error();
  return key;
}
function password(value) {
  if (typeof value !== 'string' || value.length < 16 || value.length > 1024) throw new Error();
  return value;
}
try {
  const raw = readFileSync(0);
  if (raw.length > MAX) throw new Error();
  const input = JSON.parse(raw.toString('utf8'));
  let result;
  if (input.operation === 'generate') {
    const keys = generateKeyPairSync('ed25519');
    result = { private_der: keys.privateKey.export({ type: 'pkcs8', format: 'der' }).toString('base64'),
      public_der: keys.publicKey.export({ type: 'spki', format: 'der' }).toString('base64') };
  } else if (input.operation === 'sign') {
    result = { signature: sign(null, bytes(input.data), privateKey(input.private_der)).toString('base64') };
  } else if (input.operation === 'verify') {
    const signature = bytes(input.signature, 64);
    if (signature.length !== 64) throw new Error();
    result = { valid: verify(null, bytes(input.data), publicKey(input.public_der), signature) };
  } else if (input.operation === 'derive_public') {
    result = { public_der: createPublicKey(privateKey(input.private_der)).export({ type: 'spki', format: 'der' }).toString('base64') };
  } else if (input.operation === 'seal') {
    const salt = randomBytes(16), nonce = randomBytes(12);
    const key = scryptSync(password(input.password), salt, 32, { N: 32768, r: 8, p: 1, maxmem: 64 * 1024 * 1024 });
    const cipher = createCipheriv('aes-256-gcm', key, nonce);
    cipher.setAAD(Buffer.from('DesktopStats.publisher-backup.v1'));
    const ciphertext = Buffer.concat([cipher.update(bytes(input.data)), cipher.final()]);
    result = { schema: 1, scheme: 'scrypt-32768-8-1/aes-256-gcm', salt: salt.toString('base64'),
      nonce: nonce.toString('base64'), ciphertext: ciphertext.toString('base64'), tag: cipher.getAuthTag().toString('base64') };
    key.fill(0);
  } else if (input.operation === 'open') {
    const b = input.backup;
    if (!b || b.schema !== 1 || b.scheme !== 'scrypt-32768-8-1/aes-256-gcm') throw new Error();
    const salt = bytes(b.salt, 16), nonce = bytes(b.nonce, 12), tag = bytes(b.tag, 16);
    if (salt.length !== 16 || nonce.length !== 12 || tag.length !== 16) throw new Error();
    const key = scryptSync(password(input.password), salt, 32, { N: 32768, r: 8, p: 1, maxmem: 64 * 1024 * 1024 });
    const cipher = createDecipheriv('aes-256-gcm', key, nonce);
    cipher.setAAD(Buffer.from('DesktopStats.publisher-backup.v1')); cipher.setAuthTag(tag);
    const plaintext = Buffer.concat([cipher.update(bytes(b.ciphertext)), cipher.final()]);
    result = { data: plaintext.toString('base64') }; key.fill(0);
  } else throw new Error();
  process.stdout.write(JSON.stringify(result));
} catch {
  // Do not echo keys, passwords, inputs, provider errors or stack traces.
  process.stderr.write('Publisher cryptographic operation failed.');
  process.exitCode = 1;
}
