import QtQuick
import QtQuick3D

Node {
    id: rOOT
    /** 贴图路径，可动态更换；支持相对路径（相对 Dvd.qml 所在目录）或 file:// 绝对路径 */
    property string textureSource: "maps/0.png"
    /** 由 dvd_scene 注入，用于 hover 判断 */
    property int delegateIndex: -1
    /** 展开状态：横着时再次点击触发展开，back 不动，spine 沿 back 轴转 -90°，front 沿 spine 转后再沿自身轴转 -90° */
    property bool expanded: false

    Model {
        id: cD
        eulerRotation.x: 90
        eulerRotation.y: 90

        source: "meshes/cD.mesh"

        PrincipledMaterial {
            id: transparent_material
            baseColor: "#60cccccc"
            metalness: 0
            roughness: 0.0727273
            cullMode: Material.NoCulling
            alphaMode: PrincipledMaterial.Blend
            depthDrawMode: Material.OpaquePrePassDepthDraw
        }

        PrincipledMaterial {
            id: rainbow_material
            baseColor: "#ffcccccc"
            metalness: 0.9
            roughness: 0.15
            cullMode: Material.NoCulling
        }
        materials: [
            pic_material,
            transparent_material,
            rainbow_material
        ]
    }
    
    PrincipledMaterial {
        id: pic_material
        baseColorMap: Texture {
            source: rOOT.textureSource
            tilingModeHorizontal: Texture.Repeat
            tilingModeVertical: Texture.Repeat
        }
        opacityChannel: Material.A
        metalness: 0
        roughness: 0.08
        cullMode: Material.NoCulling
    }

    PrincipledMaterial {
        id: trans_material
        baseColor: "#FFFFFFFF"
        metalness: 0
        roughness: 0.3
        cullMode: Material.NoCulling
        alphaMode: PrincipledMaterial.Blend
        depthDrawMode: Material.OpaquePrePassDepthDraw
    }

    // back 不动
    Model {
        id: back
        source: "meshes/back.mesh"
        pickable: true
        materials: [pic_material, trans_material]
    }

    // spine 沿 back 的轴（Y 轴）转 -90°，pivot 设在 back-spine 接缝（spine 左缘）
    Node {
        id: spineNode
        x:-0.006707
        z:-0.000293
        eulerRotation.y: expanded ? -90 : 0
        Behavior on eulerRotation.y {
            NumberAnimation { duration: 350; easing.type: Easing.OutCubic }
        }

        Model {
            id: spine
            x:0.006707
            z:0.000293
            source: "meshes/spine.mesh"
            pickable: true
            materials: [pic_material, trans_material]
        }

        // front 在 spine 转的基础上沿自身轴转 -90°
        Node {
            id: frontNode
            x:0.013414
            z:0
            eulerRotation.y: expanded ? -90 : 0
            Behavior on eulerRotation.y {
                NumberAnimation { duration: 350; easing.type: Easing.OutCubic }
            }

            Model {
                id: front
            x:-0.006707
            z:0.000293
                source: "meshes/front.mesh"
                pickable: true
                materials: [pic_material, trans_material]
            }
        }
    }
}
