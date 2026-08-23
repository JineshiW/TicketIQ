import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
} from "react";
import {
  Canvas,
  useFrame,
  useThree,
} from "@react-three/fiber";
import {
  OrbitControls,
  PerspectiveCamera,
} from "@react-three/drei";
import * as THREE from "three";

import type {
  Cluster,
  ClusterTicket,
} from "@/types";
import {
  colorForKey,
  truncate,
} from "@/lib/format";

interface GraphNode {
  id: string;
  ticket: ClusterTicket;
  cluster: Cluster;
  color: string;
  position: [number, number, number];
  velocity: THREE.Vector3;
}

interface GraphLink {
  source: string;
  target: string;
  clusterId: string;
  color: string;
}

interface Props {
  clusters: Cluster[];
}

interface NodeProps {
  node: GraphNode;
  hovered: string | null;
  onHover: (node: GraphNode | null) => void;
}

interface LinkProps {
  source: GraphNode;
  target: GraphNode;
  highlighted: boolean;
  color: string;
}

/* -------------------------------------------------------
 * Helpers
 * ----------------------------------------------------- */

function resolveThreeColor(
  color: string,
): string {
  if (!color) {
    return "#8b93a7";
  }

  if (color.trim().startsWith("var(")) {
    const variableName = color
      .trim()
      .replace(/^var\(/, "")
      .replace(/\)$/, "")
      .trim();

    const resolved = getComputedStyle(
      document.documentElement,
    )
      .getPropertyValue(variableName)
      .trim();

    if (resolved) {
      return resolved;
    }
  }

  return color;
}

function seededRandom(seed: number) {
  let value = seed;

  return () => {
    value =
      (value * 9301 + 49297) %
      233280;

    return value / 233280;
  };
}

function initialPosition(
  clusterIndex: number,
  ticketIndex: number,
  clusterCount: number,
  ticketCount: number,
): [number, number, number] {
  const random = seededRandom(
    (clusterIndex + 1) * 10000 +
      (ticketIndex + 1) * 997 +
      clusterCount * 31 +
      ticketCount,
  );

  const phi =
    Math.acos(
      1 -
        (2 * (clusterIndex + 0.5)) /
          Math.max(clusterCount, 1),
    );

  const theta =
    Math.PI *
    (3 - Math.sqrt(5)) *
    clusterIndex;

  const clusterRadius = 8;

  const centerX =
    Math.cos(theta) *
    Math.sin(phi) *
    clusterRadius;

  const centerY =
    Math.cos(phi) *
    clusterRadius;

  const centerZ =
    Math.sin(theta) *
    Math.sin(phi) *
    clusterRadius;

  const spread = Math.max(
    1.2,
    Math.min(3.2, ticketCount * 0.12),
  );

  return [
    centerX +
      (random() - 0.5) * spread,

    centerY +
      (random() - 0.5) * spread,

    centerZ +
      (random() - 0.5) * spread,
  ];
}

/*
 * Build an explicit repository + type key.
 *
 * Example:
 *
 * kubernetes/kubernetes::bug
 * prometheus/prometheus::bug
 *
 * This means identical labels from different repositories
 * remain separate 3D clusters.
 */
function clusterIdentity(
  cluster: Cluster,
): string {
  return `${cluster.repository}::${cluster.type}::${cluster.cluster_key}`;
}

/* -------------------------------------------------------
 * Camera
 * ----------------------------------------------------- */

function CameraRig({
  controlsRef,
  idle,
}: {
  controlsRef: MutableRefObject<any>;
  idle: boolean;
}) {
  const { camera } = useThree();

  useFrame((_, delta) => {
    if (
      !idle ||
      !controlsRef.current
    ) {
      return;
    }

    const controls =
      controlsRef.current;

    const offset =
      camera.position.clone();

    const radius = Math.sqrt(
      offset.x * offset.x +
        offset.z * offset.z,
    );

    const angle = Math.atan2(
      offset.z,
      offset.x,
    );

    const nextAngle =
      angle + delta * 0.055;

    camera.position.x =
      Math.cos(nextAngle) *
      radius;

    camera.position.z =
      Math.sin(nextAngle) *
      radius;

    controls.update();
  });

  return null;
}

/* -------------------------------------------------------
 * Links
 * ----------------------------------------------------- */

function NetworkLink({
  source,
  target,
  highlighted,
  color,
}: LinkProps) {
  const geometry = useMemo(() => {
    const points = [
      new THREE.Vector3(
        ...source.position,
      ),
      new THREE.Vector3(
        ...target.position,
      ),
    ];

    return new THREE.BufferGeometry().setFromPoints(
      points,
    );
  }, [
    source.position,
    target.position,
  ]);

  const material = useMemo(
    () =>
      new THREE.LineBasicMaterial({
        color: highlighted
          ? "#ffffff"
          : color || "#d9dce3",
        transparent: true,
        opacity: highlighted
          ? 0.95
          : 0.42,
      }),
    [highlighted, color],
  );

  useEffect(() => {
    return () => {
      geometry.dispose();
      material.dispose();
    };
  }, [geometry, material]);

  return (
    <primitive
      object={
        new THREE.Line(
          geometry,
          material,
        )
      }
    />
  );
}

/* -------------------------------------------------------
 * Ticket node
 * ----------------------------------------------------- */

function NetworkNode({
  node,
  hovered,
  onHover,
}: NodeProps) {
  const meshRef =
    useRef<THREE.Mesh>(null);

  const isHovered =
    hovered === node.id;

  const threeColor = useMemo(
    () =>
      resolveThreeColor(
        node.color,
      ),
    [node.color],
  );

  useFrame((state) => {
    if (!meshRef.current) {
      return;
    }

    const t =
      state.clock.getElapsedTime();

    meshRef.current.position.y +=
      Math.sin(
        t * 0.65 +
          node.id.length,
      ) * 0.0007;

    const targetScale =
      isHovered ? 1.9 : 1;

    meshRef.current.scale.lerp(
      new THREE.Vector3(
        targetScale,
        targetScale,
        targetScale,
      ),
      0.12,
    );
  });

  return (
    <mesh
      ref={meshRef}
      position={node.position}
      onPointerEnter={(event) => {
        event.stopPropagation();
        onHover(node);
      }}
      onPointerLeave={(event) => {
        event.stopPropagation();
        onHover(null);
      }}
    >
      <sphereGeometry
        args={[
          isHovered
            ? 0.17
            : 0.115,
          20,
          20,
        ]}
      />

      <meshStandardMaterial
        color={threeColor}
        emissive={threeColor}
        emissiveIntensity={
          isHovered ? 3.2 : 1.45
        }
        transparent
        opacity={
          isHovered ? 1 : 0.82
        }
        roughness={0.22}
        metalness={0.25}
      />

      {isHovered ? (
        <pointLight
          color={threeColor}
          intensity={2.4}
          distance={3}
        />
      ) : null}
    </mesh>
  );
}

/* -------------------------------------------------------
 * Force simulation
 * ----------------------------------------------------- */

function ForceNetwork({
  nodes,
  links,
  hovered,
  onHover,
}: {
  nodes: GraphNode[];
  links: GraphLink[];
  hovered: string | null;
  onHover: (
    node: GraphNode | null,
  ) => void;
}) {
  const nodeMap = useMemo(() => {
    const map =
      new Map<string, GraphNode>();

    nodes.forEach((node) => {
      map.set(node.id, node);
    });

    return map;
  }, [nodes]);

  useFrame(
    (state, delta) => {
      const safeDelta =
        Math.min(delta, 0.033);

      /*
       * Soft central gravity.
       */
      for (const node of nodes) {
        const position =
          new THREE.Vector3(
            ...node.position,
          );

        const gravity =
          position
            .clone()
            .multiplyScalar(-0.004);

        node.velocity.add(
          gravity,
        );

        const time =
          state.clock.getElapsedTime();

        node.velocity.x +=
          Math.sin(
            time * 0.17 +
              node.id.length,
          ) * 0.0008;

        node.velocity.y +=
          Math.cos(
            time * 0.13 +
              node.id.length,
          ) * 0.0007;

        node.velocity.z +=
          Math.sin(
            time * 0.11 +
              node.id.length * 2,
          ) * 0.0008;
      }

      /*
       * Repulsion.
       */
      for (
        let i = 0;
        i < nodes.length;
        i += 1
      ) {
        for (
          let j = i + 1;
          j < nodes.length;
          j += 1
        ) {
          const a = nodes[i];
          const b = nodes[j];

          let dx =
            a.position[0] -
            b.position[0];

          let dy =
            a.position[1] -
            b.position[1];

          let dz =
            a.position[2] -
            b.position[2];

          const distanceSquared =
            dx * dx +
            dy * dy +
            dz * dz;

          if (
            distanceSquared <
            0.001
          ) {
            dx = 0.01;
            dy = 0.01;
            dz = 0.01;
          }

          const distance =
            Math.sqrt(
              distanceSquared,
            );

          if (
            distance < 4.2
          ) {
            const force =
              ((4.2 - distance) /
                4.2) *
              0.004;

            const nx =
              dx / distance;

            const ny =
              dy / distance;

            const nz =
              dz / distance;

            a.velocity.x +=
              nx * force;

            a.velocity.y +=
              ny * force;

            a.velocity.z +=
              nz * force;

            b.velocity.x -=
              nx * force;

            b.velocity.y -=
              ny * force;

            b.velocity.z -=
              nz * force;
          }
        }
      }

      /*
       * Attraction only occurs inside the
       * repository-specific cluster.
       *
       * Because the backend supplies separate
       * cluster_key values per repository,
       * links never connect Kubernetes tickets
       * to Prometheus tickets.
       */
      for (const link of links) {
        const source =
          nodeMap.get(
            link.source,
          );

        const target =
          nodeMap.get(
            link.target,
          );

        if (
          !source ||
          !target
        ) {
          continue;
        }

        /*
         * Extra safety:
         *
         * Never connect tickets belonging
         * to different repositories.
         */
        if (
          source.cluster.repository !==
          target.cluster.repository
        ) {
          continue;
        }

        const dx =
          target.position[0] -
          source.position[0];

        const dy =
          target.position[1] -
          source.position[1];

        const dz =
          target.position[2] -
          source.position[2];

        const distance =
          Math.sqrt(
            dx * dx +
              dy * dy +
              dz * dz,
          );

        if (distance === 0) {
          continue;
        }

        const desiredDistance =
          2.1;

        const force =
          (distance -
            desiredDistance) *
          0.002;

        const nx =
          dx / distance;

        const ny =
          dy / distance;

        const nz =
          dz / distance;

        source.velocity.x +=
          nx * force;

        source.velocity.y +=
          ny * force;

        source.velocity.z +=
          nz * force;

        target.velocity.x -=
          nx * force;

        target.velocity.y -=
          ny * force;

        target.velocity.z -=
          nz * force;
      }

      /*
       * Apply velocity.
       */
      for (const node of nodes) {
        node.velocity.multiplyScalar(
          0.965,
        );

        node.position[0] +=
          node.velocity.x *
          safeDelta *
          60;

        node.position[1] +=
          node.velocity.y *
          safeDelta *
          60;

        node.position[2] +=
          node.velocity.z *
          safeDelta *
          60;

        const maxRadius = 14;

        const radius =
          Math.sqrt(
            node.position[0] **
              2 +
              node.position[1] **
                2 +
              node.position[2] **
                2,
          );

        if (
          radius > maxRadius
        ) {
          const scale =
            maxRadius /
            radius;

          node.position[0] *=
            scale;

          node.position[1] *=
            scale;

          node.position[2] *=
            scale;

          node.velocity.multiplyScalar(
            0.5,
          );
        }
      }
    },
  );

  return (
    <>
      {links.map(
        (link, index) => {
          const source =
            nodeMap.get(
              link.source,
            );

          const target =
            nodeMap.get(
              link.target,
            );

          if (
            !source ||
            !target
          ) {
            return null;
          }

          const highlighted =
            hovered ===
              source.id ||
            hovered ===
              target.id;

          return (
            <NetworkLink
              key={`${link.source}-${link.target}-${index}`}
              source={source}
              target={target}
              highlighted={
                highlighted
              }
              color={link.color}
            />
          );
        },
      )}

      {nodes.map((node) => (
        <NetworkNode
          key={node.id}
          node={node}
          hovered={hovered}
          onHover={onHover}
        />
      ))}
    </>
  );
}

/* -------------------------------------------------------
 * Zoom controls
 * ----------------------------------------------------- */

function CameraControls({
  controlsRef,
}: {
  controlsRef: MutableRefObject<any>;
}) {
  const zoom = useCallback(
    (amount: number) => {
      const controls =
        controlsRef.current;

      if (!controls) {
        return;
      }

      const camera =
        controls.object as THREE.PerspectiveCamera;

      const target =
        controls.target.clone();

      const direction =
        camera.position
          .clone()
          .sub(target);

      direction.multiplyScalar(
        amount,
      );

      camera.position.copy(
        target
          .clone()
          .add(direction),
      );

      controls.update();
    },
    [],
  );

  return (
    <div
      style={{
        position: "absolute",
        right: 14,
        top: 14,
        display: "flex",
        gap: 6,
        zIndex: 10,
      }}
    >
      <button
        type="button"
        className="btn btn--ghost btn--sm"
        onClick={() =>
          zoom(0.78)
        }
        title="Zoom in"
      >
        +
      </button>

      <button
        type="button"
        className="btn btn--ghost btn--sm"
        onClick={() =>
          zoom(1.28)
        }
        title="Zoom out"
      >
        −
      </button>
    </div>
  );
}

/* -------------------------------------------------------
 * Main component
 * ----------------------------------------------------- */

export function ClusterScatter({
  clusters,
}: Props) {
  const [hovered, setHovered] =
    useState<GraphNode | null>(
      null,
    );

  const controlsRef =
    useRef<any>(null);

  const [idle, setIdle] =
    useState(true);

  const idleTimerRef =
    useRef<number | null>(
      null,
    );

  /*
   * Convert backend clusters into
   * repository-aware 3D nodes.
   */
  const {
    nodes,
    links,
    types,
  } = useMemo(() => {
    const generatedNodes:
      GraphNode[] = [];

    const generatedLinks:
      GraphLink[] = [];

    const validClusters =
      clusters.filter(
        (cluster) =>
          cluster.tickets.length >
          0,
      );

    const clusterCount =
      validClusters.length;

    /*
     * Each backend cluster represents:
     *
     * repository + label + cluster
     *
     * rather than label alone.
     */
    validClusters.forEach(
      (
        cluster,
        clusterIndex,
      ) => {
        const tickets =
          cluster.tickets;

        const identity =
          clusterIdentity(
            cluster,
          );

        tickets.forEach(
          (
            ticket,
            ticketIndex,
          ) => {
            const position =
              initialPosition(
                clusterIndex,
                ticketIndex,
                clusterCount,
                tickets.length,
              );

            const isUnclustered =
              cluster.cluster_id ===
              -1;

            generatedNodes.push({
              /*
               * Repository is explicitly
               * included in the node identity.
               */
              id: `${identity}:${ticket.id}`,

              ticket,

              cluster,

              color:
                isUnclustered
                  ? "rgba(150, 160, 180, 0.7)"
                  : colorForKey(
                      cluster.type,
                    ),

              position,

              velocity:
                new THREE.Vector3(),
            });
          },
        );
      },
    );

    /*
     * Build links only inside the
     * same repository-specific cluster.
     */
    validClusters.forEach(
      (cluster) => {
        const identity =
          clusterIdentity(
            cluster,
          );

        const clusterNodes =
          generatedNodes.filter(
            (node) =>
              clusterIdentity(
                node.cluster,
              ) === identity,
          );

        for (
          let i = 0;
          i <
          clusterNodes.length;
          i += 1
        ) {
          const current =
            clusterNodes[i];

          if (
            clusterNodes.length >
            1
          ) {
            const next =
              clusterNodes[
                (i + 1) %
                  clusterNodes.length
              ];

            if (
              current.id !==
              next.id
            ) {
              generatedLinks.push(
                {
                  source:
                    current.id,

                  target:
                    next.id,

                  clusterId:
                    identity,

                  color:
                    "#d9dce3",
                },
              );
            }
          }

          /*
           * Secondary constellation
           * connection.
           */
          if (
            clusterNodes.length >
            3
          ) {
            const offset =
              (i + 3) %
              clusterNodes.length;

            const secondary =
              clusterNodes[
                offset
              ];

            if (
              secondary &&
              current.id !==
                secondary.id
            ) {
              generatedLinks.push(
                {
                  source:
                    current.id,

                  target:
                    secondary.id,

                  clusterId:
                    identity,

                  color:
                    "#d9dce3",
                },
              );
            }
          }
        }
      },
    );

    /*
     * Legend remains label-based.
     *
     * Therefore:
     *
     * Kubernetes bug
     * Prometheus bug
     *
     * can both use the same "bug"
     * colour while still being separate
     * repository-specific clusters.
     */
    const typeList = [
      ...new Set(
        validClusters
          .filter(
            (cluster) =>
              cluster.cluster_id !==
              -1,
          )
          .map(
            (cluster) =>
              cluster.type,
          ),
      ),
    ];

    return {
      nodes: generatedNodes,
      links: generatedLinks,
      types: typeList,
    };
  }, [clusters]);

  /*
   * Reset cinematic rotation timer
   * after interaction.
   */
  const handleInteractionStart =
    useCallback(() => {
      setIdle(false);

      if (
        idleTimerRef.current !==
        null
      ) {
        window.clearTimeout(
          idleTimerRef.current,
        );
      }
    }, []);

  const handleInteractionEnd =
    useCallback(() => {
      if (
        idleTimerRef.current !==
        null
      ) {
        window.clearTimeout(
          idleTimerRef.current,
        );
      }

      idleTimerRef.current =
        window.setTimeout(() => {
          setIdle(true);
        }, 3500);
    }, []);

  useEffect(() => {
    return () => {
      if (
        idleTimerRef.current !==
        null
      ) {
        window.clearTimeout(
          idleTimerRef.current,
        );
      }
    };
  }, []);

  const hoveredLinks =
    useMemo(() => {
      return links;
    }, [links]);

  if (!clusters.length) {
    return (
      <div
        style={{
          minHeight: 430,
          display: "grid",
          placeItems: "center",
        }}
      >
        <p className="small dim">
          No cluster data
          available.
        </p>
      </div>
    );
  }

  return (
    <div
      className="stack"
      style={{
        gap: 12,
      }}
    >
      {/* ---------------------------------------------------
       * Legend
       * ------------------------------------------------- */}

      <div className="legend">
        {types.map((type) => (
          <span
            key={type}
            className="legend__item"
          >
            <span
              className="legend__dot"
              style={{
                background:
                  colorForKey(
                    type,
                  ),

                boxShadow: `0 0 8px ${colorForKey(
                  type,
                )}`,
              }}
            />

            {type}
          </span>
        ))}

        {clusters.some(
          (cluster) =>
            cluster.cluster_id ===
            -1,
        ) ? (
          <span className="legend__item">
            <span
              className="legend__dot"
              style={{
                background:
                  "var(--text-dim)",
              }}
            />

            Unclustered
          </span>
        ) : null}
      </div>

      {/* ---------------------------------------------------
       * 3D constellation
       * ------------------------------------------------- */}

      <div
        style={{
          position: "relative",
          width: "100%",
          height: 480,
          overflow: "hidden",
          borderRadius: 14,
          background:
            "radial-gradient(circle at 50% 45%, rgba(90, 70, 150, 0.10), rgba(5, 7, 14, 0.96) 68%)",
          border:
            "1px solid rgba(255,255,255,0.07)",
          boxShadow:
            "inset 0 0 80px rgba(0,0,0,0.35)",
        }}
      >
        <Canvas
          dpr={[1, 1.75]}
          gl={{
            antialias: true,
            alpha: true,
          }}
        >
          <PerspectiveCamera
            makeDefault
            position={[
              0,
              2,
              22,
            ]}
            fov={48}
          />

          <ambientLight
            intensity={0.45}
          />

          <pointLight
            position={[
              0,
              8,
              10,
            ]}
            intensity={1.5}
          />

          <pointLight
            position={[
              -10,
              -5,
              -8,
            ]}
            intensity={0.8}
          />

          <ForceNetwork
            nodes={nodes}
            links={hoveredLinks}
            hovered={
              hovered?.id ?? null
            }
            onHover={setHovered}
          />

          <OrbitControls
            ref={controlsRef}
            enableZoom
            enablePan
            enableRotate
            minDistance={7}
            maxDistance={40}
            dampingFactor={0.06}
            enableDamping
            onStart={
              handleInteractionStart
            }
            onEnd={
              handleInteractionEnd
            }
          />

          <CameraRig
            controlsRef={
              controlsRef
            }
            idle={idle}
          />
        </Canvas>

        <CameraControls
          controlsRef={
            controlsRef
          }
        />

        <div
          style={{
            position:
              "absolute",
            left: 14,
            bottom: 12,
            pointerEvents:
              "none",
            fontSize: 11,
            color:
              "rgba(255,255,255,0.42)",
            letterSpacing:
              "0.02em",
          }}
        >
          Drag to rotate ·
          Right-drag to pan ·
          Scroll to zoom
        </div>
      </div>

      {/* ---------------------------------------------------
       * Hover information
       * ------------------------------------------------- */}

      <div
        className="tooltip-card"
        style={{
          minHeight: 78,
          maxWidth: "100%",
          transition:
            "border-color 160ms ease, background 160ms ease",
          borderColor: hovered
            ? "rgba(255,255,255,0.16)"
            : undefined,
        }}
      >
        {hovered ? (
          <>
            <p
              className="small dim"
              style={{
                textTransform:
                  "uppercase",
                letterSpacing:
                  "0.1em",
              }}
            >
              {hovered.cluster.repository}
              {" · "}
              {hovered.cluster.type}
            </p>

            <p
              style={{
                fontWeight: 600,
                marginTop: 4,
              }}
            >
              {truncate(
                hovered.ticket.title,
                110,
              )}
            </p>

            <p
              className="small muted"
              style={{
                marginTop: 4,
              }}
            >
              {hovered.cluster.size}
              {" tickets · "}
              {truncate(
                hovered.cluster.summary,
                120,
              )}
            </p>
          </>
        ) : (
          <p className="small dim">
            Hover a ticket to
            inspect its pattern.
            The constellation
            gently rotates when
            idle.
          </p>
        )}
      </div>
    </div>
  );
}