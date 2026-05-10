import { useEffect, useRef, useState } from "react";
import type { AvatarRuntimePlacement, AvatarRuntimeState } from "../runtime/avatarRuntime";

export interface AvatarRendererProps {
  avatar: AvatarRuntimeState;
}

function CssAvatarRenderer() {
  return (
    <div className="character-shell" aria-hidden="true">
      <div className="character-shell__hair-back" />
      <div className="character-shell__face">
        <span className="eye eye-left" />
        <span className="eye eye-right" />
        <span className="mouth" />
      </div>
      <div className="bang bang-one" />
      <div className="bang bang-two" />
      <div className="bang bang-three" />
      <div className="character-shell__neck" />
      <div className="character-shell__body" />
      <div className="character-shell__collar" />
      <div className="arm arm-left" />
      <div className="arm arm-right" />
    </div>
  );
}

declare global {
  interface Window {
    PIXI?: {
      Application: new (options: Record<string, unknown>) => {
        stage: {
          addChild: (child: unknown) => void;
        };
        view: HTMLCanvasElement;
        renderer: {
          resize: (width: number, height: number) => void;
        };
        destroy: (removeView?: boolean, options?: Record<string, unknown>) => void;
      };
      live2d?: {
        Live2DModel: {
          from: (source: string) => Promise<Live2DDisplayModel>;
        };
      };
    };
    PIXI_LIVE2D_DISPLAY?: {
      Live2DModel: {
        from: (source: string) => Promise<Live2DDisplayModel>;
      };
    };
    Live2DModel?: {
      from: (source: string) => Promise<Live2DDisplayModel>;
    };
  }
}

interface Live2DDisplayModel {
  scale: {
    set: (value: number) => void;
  };
  anchor?: {
    set: (x: number, y?: number) => void;
  };
  x: number;
  y: number;
  width: number;
  height: number;
  expression?: (name: string) => void;
  motion?: (group: string, index?: number) => void;
}

const live2dScripts = [
  "https://cdn.jsdelivr.net/npm/pixi.js@6.5.10/dist/browser/pixi.min.js",
  "https://cdn.jsdelivr.net/npm/live2dcubismcore/live2dcubismcore.min.js",
  "https://cdn.jsdelivr.net/npm/pixi-live2d-display/dist/cubism4.min.js",
];

let live2dLoader: Promise<void> | null = null;

function loadScript(src: string) {
  return new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${src}"]`);
    if (existing) {
      if (existing.dataset.loaded === "true") resolve();
      else existing.addEventListener("load", () => resolve(), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.addEventListener(
      "load",
      () => {
        script.dataset.loaded = "true";
        resolve();
      },
      { once: true },
    );
    script.addEventListener("error", () => reject(new Error(`Failed to load ${src}`)), { once: true });
    document.head.appendChild(script);
  });
}

function ensureLive2DLoader() {
  if (!live2dLoader) {
    live2dLoader = live2dScripts.reduce(
      (promise, src) => promise.then(() => loadScript(src)),
      Promise.resolve(),
    );
  }
  return live2dLoader;
}

function parseLive2DMotionTarget(target: string) {
  const [group, index] = target.split(":");
  const parsedIndex = Number(index);
  return {
    group,
    index: Number.isFinite(parsedIndex) ? parsedIndex : undefined,
  };
}

function applyRuntimeBinding(model: Live2DDisplayModel, avatar: AvatarRuntimeState) {
  const expressionName = avatar.manifest.expressions[avatar.dataBindings.live2dExpression];
  const motionTarget = avatar.dataBindings.live2dMotionTarget || avatar.manifest.motions[avatar.dataBindings.live2dMotion];

  if (expressionName && typeof model.expression === "function") {
    model.expression(expressionName);
  }

  if (motionTarget && typeof model.motion === "function") {
    const { group, index } = parseLive2DMotionTarget(motionTarget);
    model.motion(group, index);
  }
}

function fitLive2DModel(
  model: Live2DDisplayModel,
  width: number,
  height: number,
  placement: AvatarRuntimePlacement,
) {
  const modelWidth = model.width || width;
  const modelHeight = model.height || height;
  const scale = Math.min(width / modelWidth, height / modelHeight) * 1.28 * placement.scaleMultiplier;
  model.scale.set(Number.isFinite(scale) && scale > 0 ? scale : 1);
  if (model.anchor) model.anchor.set(0.5, 0.5);
  model.x = width * 0.52 + placement.offsetX;
  model.y = height * 0.5 + placement.offsetY;
}

function Live2DAvatarRenderer({ avatar }: AvatarRendererProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const appRef = useRef<InstanceType<NonNullable<typeof window.PIXI>["Application"]> | null>(null);
  const modelRef = useRef<Live2DDisplayModel | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function mount() {
      try {
        await ensureLive2DLoader();
        if (cancelled || !hostRef.current || !window.PIXI) return;
        const Live2DModel =
          window.PIXI.live2d?.Live2DModel ??
          window.PIXI_LIVE2D_DISPLAY?.Live2DModel ??
          window.Live2DModel;
        if (!Live2DModel) throw new Error("Live2DModel global is unavailable.");

        const rect = hostRef.current.getBoundingClientRect();
        const width = Math.max(320, rect.width || hostRef.current.clientWidth);
        const height = Math.max(420, rect.height || hostRef.current.clientHeight);
        const app = new window.PIXI.Application({
          width,
          height,
          transparent: true,
          antialias: true,
          autoDensity: true,
          resolution: window.devicePixelRatio || 1,
        });
        app.view.className = "live2d-canvas";
        hostRef.current.replaceChildren(app.view);

        const model = await Live2DModel.from(avatar.manifest.source);
        if (cancelled) {
          app.destroy(true, { children: true, texture: true, baseTexture: true });
          return;
        }

        fitLive2DModel(model, width, height, avatar.placement);
        app.stage.addChild(model);
        appRef.current = app;
        modelRef.current = model;
        applyRuntimeBinding(model, avatar);
      } catch (error) {
        console.warn("Live2D renderer fallback:", error);
        if (!cancelled) setFailed(true);
      }
    }

    mount();

    return () => {
      cancelled = true;
      modelRef.current = null;
      appRef.current?.destroy(true, { children: true, texture: true, baseTexture: true });
      appRef.current = null;
    };
  }, [avatar.manifest.source]);

  useEffect(() => {
    if (modelRef.current) applyRuntimeBinding(modelRef.current, avatar);
  }, [avatar]);

  useEffect(() => {
    if (!modelRef.current || !hostRef.current) return;
    const rect = hostRef.current.getBoundingClientRect();
    const width = Math.max(320, rect.width || hostRef.current.clientWidth);
    const height = Math.max(420, rect.height || hostRef.current.clientHeight);
    appRef.current?.renderer.resize(width, height);
    fitLive2DModel(modelRef.current, width, height, avatar.placement);
  }, [avatar.placement.offsetX, avatar.placement.offsetY, avatar.placement.scaleMultiplier, avatar.runtimeRevision]);

  if (failed) return <CssAvatarRenderer />;

  return (
    <div
      ref={hostRef}
      className="avatar-live2d-mount"
      aria-hidden="true"
      data-avatar-manifest={avatar.manifest.id}
      data-avatar-source={avatar.manifest.source}
      data-live2d-motion-target={avatar.dataBindings.live2dMotionTarget}
    />
  );
}

function FutureAvatarRenderer({ avatar }: AvatarRendererProps) {
  return (
    <div
      className="avatar-runtime-mount"
      aria-hidden="true"
      data-avatar-manifest={avatar.manifest.id}
      data-avatar-source={avatar.manifest.source}
      data-avatar-renderer={avatar.manifest.renderer}
    >
      <CssAvatarRenderer />
    </div>
  );
}

export function AvatarRenderer({ avatar }: AvatarRendererProps) {
  if (avatar.renderer === "css_placeholder") return <CssAvatarRenderer />;
  if (avatar.renderer === "live2d_ready") return <Live2DAvatarRenderer avatar={avatar} />;
  return <FutureAvatarRenderer avatar={avatar} />;
}
