import {
  Box3,
  BufferGeometry,
  Color,
  Material,
  Mesh,
  MeshStandardMaterial,
  Object3D,
  Texture,
  Vector3,
} from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

export const SUPPORTED_EXTENSIONS = ['stl', 'obj', 'glb', 'gltf'] as const;
export type ModelFormat = (typeof SUPPORTED_EXTENSIONS)[number];
export const MAX_FILE_BYTES = 300 * 1024 * 1024;

export interface LoadedModel {
  object: Object3D;
  format: ModelFormat;
  name: string;
  /** Non-fatal notes for the user (e.g. missing materials). */
  warnings: string[];
}

export class ModelLoadError extends Error {}

export function getExtension(filename: string): string {
  const i = filename.lastIndexOf('.');
  return i < 0 ? '' : filename.slice(i + 1).toLowerCase();
}

export type FileValidation = { ok: true; format: ModelFormat } | { ok: false; error: string };

export function validateModelFile(file: { name: string; size: number }): FileValidation {
  const ext = getExtension(file.name);
  if (!(SUPPORTED_EXTENSIONS as readonly string[]).includes(ext)) {
    return { ok: false, error: `Unsupported file type ".${ext || '?'}". Use STL, OBJ, GLB or glTF.` };
  }
  if (file.size === 0) return { ok: false, error: 'The selected file is empty.' };
  if (file.size > MAX_FILE_BYTES) {
    return { ok: false, error: `File is too large (limit ${MAX_FILE_BYTES / 1024 / 1024} MB).` };
  }
  return { ok: true, format: ext as ModelFormat };
}

/** True if a glTF JSON document references buffers/images that are not embedded data URIs. */
export function gltfHasExternalResources(json: unknown): boolean {
  if (typeof json !== 'object' || json === null) return false;
  const doc = json as { buffers?: { uri?: unknown }[]; images?: { uri?: unknown }[] };
  const external = (list?: { uri?: unknown }[]) =>
    Array.isArray(list) && list.some((r) => typeof r?.uri === 'string' && !r.uri.startsWith('data:'));
  return external(doc.buffers) || external(doc.images);
}

const EXTERNAL_GLTF_MESSAGE =
  'This .gltf references external files (.bin / textures) that a single-file upload cannot provide. ' +
  'Export it as a self-contained .glb (or embed resources) and try again.';

function countMeshes(root: Object3D): number {
  let n = 0;
  root.traverse((o) => {
    if ((o as Mesh).isMesh) n += 1;
  });
  return n;
}

function parseGltf(loader: GLTFLoader, data: ArrayBuffer | string): Promise<Object3D> {
  return new Promise((resolve, reject) => {
    loader.parse(data, '', (gltf) => resolve(gltf.scene), (err) => reject(err));
  });
}

/** Load a local file entirely in the browser. Never uploads anything. */
export async function loadModelFile(file: File): Promise<LoadedModel> {
  const check = validateModelFile(file);
  if (!check.ok) throw new ModelLoadError(check.error);
  const warnings: string[] = [];
  let object: Object3D;

  try {
    switch (check.format) {
      case 'stl': {
        const geometry = new STLLoader().parse(await file.arrayBuffer());
        if (!geometry.getAttribute('position') || geometry.getAttribute('position').count === 0) {
          throw new ModelLoadError('The STL file contains no geometry.');
        }
        if (!geometry.getAttribute('normal')) geometry.computeVertexNormals();
        const material = new MeshStandardMaterial({
          color: new Color('#c9d3ff'),
          metalness: 0.15,
          roughness: 0.5,
          vertexColors: (geometry as BufferGeometry & { hasColors?: boolean }).hasColors === true,
        });
        object = new Mesh(geometry, material);
        break;
      }
      case 'obj': {
        object = new OBJLoader().parse(await file.text());
        if (countMeshes(object) === 0) throw new ModelLoadError('The OBJ file contains no renderable geometry.');
        warnings.push('OBJ materials (.mtl) are not loaded; default shading is used.');
        break;
      }
      case 'glb': {
        object = await parseGltf(new GLTFLoader(), await file.arrayBuffer());
        break;
      }
      case 'gltf': {
        const text = await file.text();
        let json: unknown;
        try {
          json = JSON.parse(text);
        } catch {
          throw new ModelLoadError('The glTF file is not valid JSON.');
        }
        if (gltfHasExternalResources(json)) throw new ModelLoadError(EXTERNAL_GLTF_MESSAGE);
        object = await parseGltf(new GLTFLoader(), text);
        break;
      }
    }
  } catch (err) {
    if (err instanceof ModelLoadError) throw err;
    const detail = err instanceof Error ? err.message : typeof err === 'string' ? err : 'unknown error';
    throw new ModelLoadError(`Could not read "${file.name}": ${detail}`);
  }

  if (countMeshes(object) === 0) {
    disposeObject(object);
    throw new ModelLoadError('The file loaded but contains no renderable meshes.');
  }
  const box = new Box3().setFromObject(object);
  if (box.isEmpty() || !box.getSize(new Vector3()).toArray().every(Number.isFinite)) {
    disposeObject(object);
    throw new ModelLoadError('The model has invalid or empty bounds.');
  }
  return { object, format: check.format, name: file.name, warnings };
}

function disposeMaterial(material: Material): void {
  for (const value of Object.values(material)) {
    if (value && (value as Texture).isTexture) (value as Texture).dispose();
  }
  material.dispose();
}

/** Release GPU resources owned by an object tree. */
export function disposeObject(root: Object3D): void {
  root.traverse((o) => {
    const mesh = o as Mesh;
    if (!mesh.isMesh) return;
    (mesh.geometry as BufferGeometry | undefined)?.dispose();
    const mat = mesh.material;
    if (Array.isArray(mat)) mat.forEach(disposeMaterial);
    else if (mat) disposeMaterial(mat);
  });
}
