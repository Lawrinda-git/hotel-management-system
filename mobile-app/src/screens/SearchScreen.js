import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, FlatList } from 'react-native';
import { API_BASE_URL } from '../config/api';

const SearchScreen = ({ navigation }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [hotels, setHotels] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/booking/options/`)
      .then(res => res.json())
      .then(data => {
        const uniqueHotels = [];
        const seen = new Set();
        for (const room of data.results || []) {
          const key = room.hotel?.id || room.hotel?.hotel_name;
          if (key && !seen.has(key)) {
            seen.add(key);
            uniqueHotels.push({
              id: room.hotel?.id || key,
              name: room.hotel?.hotel_name || 'Unknown Hotel',
              location: 'Ghana',
            });
          }
        }
        setHotels(uniqueHotels);
      })
      .catch(() => {});
  }, []);

  return (
    <View style={{ flex: 1, backgroundColor: '#f7f9fb' }}>
      <View style={{ padding: 20 }}>
        <Text style={{ fontSize: 20, fontWeight: '600', color: '#00288e', marginBottom: 16 }}>
          Search Hotels
        </Text>
        <TextInput
          placeholder="Search hotels in Ghana..."
          value={searchQuery}
          onChangeText={setSearchQuery}
          style={{
            backgroundColor: '#ffffff',
            borderRadius: 12,
            padding: 16,
            elevation: 2,
          }}
        />
      </View>
      
      <FlatList
        data={hotels.filter(h => h.name.toLowerCase().includes(searchQuery.toLowerCase()))}
        keyExtractor={(item) => item.id.toString()}
        renderItem={({ item }) => (
          <TouchableOpacity style={{
            backgroundColor: '#ffffff',
            marginHorizontal: 20,
            marginBottom: 12,
            borderRadius: 12,
            padding: 16,
            elevation: 1,
          }}>
            <Text style={{ fontSize: 16, fontWeight: '600', color: '#191c1e' }}>{item.name}</Text>
            <Text style={{ color: '#444653', marginTop: 4 }}>{item.location}</Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );
};

export default SearchScreen;