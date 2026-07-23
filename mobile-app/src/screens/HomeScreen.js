import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Image, RefreshControl } from 'react-native';

const HomeScreen = ({ navigation }) => {
  const [rooms, setRooms] = useState([]);
  const [refreshing, setRefreshing] = useState(false);

  const fetchRooms = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/mobile/rooms/');
      const data = await response.json();
      setRooms(data.rooms);
    } catch (error) {
      console.error('Failed to fetch rooms:', error);
    }
  };

  useEffect(() => {
    fetchRooms();
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchRooms();
    setRefreshing(false);
  };

  return (
    <View style={{ flex: 1, backgroundColor: '#f7f9fb' }}>
      <View style={{ padding: 20 }}>
        <Text style={{ fontSize: 24, fontWeight: '700', color: '#00288e' }}>StayHub</Text>
        <Text style={{ color: '#444653', marginTop: 4 }}>Luxury Stays in Ghana</Text>
      </View>
      
      <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
        {rooms.map((room) => (
          <TouchableOpacity 
            key={room.id} 
            style={{
              backgroundColor: '#ffffff',
              marginHorizontal: 20,
              marginBottom: 16,
              borderRadius: 16,
              padding: 16,
              elevation: 2,
            }}
          >
            <Text style={{ fontSize: 18, fontWeight: '600', color: '#191c1e' }}>
              Room {room.room_number}
            </Text>
            <Text style={{ color: '#444653' }}>{room.type}</Text>
            <Text style={{ color: '#00288e', fontWeight: '600', marginTop: 8 }}>
              GH₵{room.price_per_night}/night
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
};

export default HomeScreen;