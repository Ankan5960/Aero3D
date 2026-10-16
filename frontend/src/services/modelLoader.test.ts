import { describe, expect, it } from 'vitest';
import { BufferGeometry, Mesh, MeshStandardMaterial, BoxGeometry } from 'three';
import {
  disposeObject,
  gltfHasExternalResources,
  loadModelFile,
  validateModelFile,
} from './modelLoader';

const ASCII_STL = `solid t
facet normal 0 0 1
 outer loop
  vertex 0 0 0
  vertex 1 0 0
  vertex 0 1 0
 endloop
endfacet
endsolid t
`;
const OBJ = 'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n';
const file = (content: string, name: string) => new File([content], name);

describe('validateModelFile', () => {
  it('accepts supported extensions case-insensitively', () => {
    for (const n of ['a.stl', 'a.OBJ', 'a.glb', 'a.GLTF']) {
      expect(validateModelFile({ name: n, size: 10 }).ok).toBe(true);
    }
  });
  it('rejects unsupported, empty and oversized files', () => {
    expect(validateModelFile({ name: 'a.fbx', size: 10 })).toMatchObject({ ok: false });
    expect(validateModelFile({ name: 'noext', size: 10 })).toMatchObject({ ok: false });
    expect(validateModelFile({ name: 'a.stl', size: 0 })).toMatchObject({ ok: false });
    expect(validateModelFile({ name: 'a.stl', size: 1e10 })).toMatchObject({ ok: false });
  });
});

describe('gltfHasExternalResources', () => {
  it('detects external buffers/images but allows data URIs', () => {
    expect(gltfHasExternalResources({ buffers: [{ uri: 'model.bin' }] })).toBe(true);
    expect(gltfHasExternalResources({ images: [{ uri: 'tex.png' }] })).toBe(true);
    expect(gltfHasExternalResources({ buffers: [{ uri: 'data:application/octet-stream;base64,AA==' }] })).toBe(false);
    expect(gltfHasExternalResources({})).toBe(false);
    expect(gltfHasExternalResources(null)).toBe(false);
  });
});

describe('loadModelFile', () => {
  it('loads an ASCII STL into a mesh', async () => {
    const m = await loadModelFile(file(ASCII_STL, 'tri.stl'));
    expect(m.format).toBe('stl');
    expect((m.object as Mesh).isMesh).toBe(true);
    disposeObject(m.object);
  });

  it('loads an OBJ without materials and warns', async () => {
    const m = await loadModelFile(file(OBJ, 'tri.obj'));
    expect(m.format).toBe('obj');
    expect(m.warnings.length).toBeGreaterThan(0);
    disposeObject(m.object);
  });

  it('rejects unsupported, empty, and corrupt files with readable errors', async () => {
    await expect(loadModelFile(file('x', 'a.fbx'))).rejects.toThrow(/Unsupported/);
    await expect(loadModelFile(file('', 'a.stl'))).rejects.toThrow(/empty/);
    await expect(loadModelFile(file('this is not an stl', 'a.stl'))).rejects.toThrow();
    await expect(loadModelFile(file('just text', 'a.obj'))).rejects.toThrow(/no renderable geometry/);
    await expect(loadModelFile(file('not json', 'a.gltf'))).rejects.toThrow(/not valid JSON/);
    await expect(loadModelFile(file('garbage', 'a.glb'))).rejects.toThrow();
  });

  it('explains external-resource limitation for standalone glTF', async () => {
    const gltf = JSON.stringify({ asset: { version: '2.0' }, buffers: [{ uri: 'm.bin', byteLength: 1 }] });
    await expect(loadModelFile(file(gltf, 'm.gltf'))).rejects.toThrow(/\.glb/);
  });
});

describe('disposeObject', () => {
  it('disposes geometry and materials', () => {
    const geo = new BoxGeometry();
    const mat = new MeshStandardMaterial();
    let g = 0;
    let m = 0;
    geo.addEventListener('dispose', () => g++);
    mat.addEventListener('dispose', () => m++);
    disposeObject(new Mesh(geo as BufferGeometry, mat));
    expect([g, m]).toEqual([1, 1]);
  });
});
