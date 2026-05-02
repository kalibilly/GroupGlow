import React from 'react';
import { Canvas } from '@react-three/fiber';

function FloatingBoard({ question }) {
  return (
    <mesh rotation={[-0.4, 0.5, 0]} position={[0, 0, 0]}>
      <boxGeometry args={[4.2, 2.4, 0.22]} />
      <meshStandardMaterial color={question ? '#1f4a8a' : '#333'} roughness={0.2} metalness={0.6} />
      <mesh position={[0, 0, 0.12]}>
        <planeGeometry args={[4, 2, 1, 1]} />
        <meshStandardMaterial color={question ? '#f5f7ff' : '#f0f0f0'} emissive={'#000000'} />
      </mesh>
    </mesh>
  );
}

export default function StageScene({ question }) {
  return (
    <div className="three-stage">
      <Canvas camera={{ position: [0, 0, 8], fov: 45 }}>
        <ambientLight intensity={0.7} />
        <directionalLight position={[5, 5, 2]} intensity={1.2} />
        <FloatingBoard question={question} />
      </Canvas>
      <div className="three-overlay">
        <h3>{question ? 'Live Question Board' : 'Waiting for host'}</h3>
        <p>{question ? question.text : 'Room is ready. The host will begin the quiz shortly.'}</p>
      </div>
    </div>
  );
}
