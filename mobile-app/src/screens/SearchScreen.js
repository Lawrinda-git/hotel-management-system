import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, FlatList } from 'react-native';

const SearchScreen = ({ navigation }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [hotels] = useState([
    { id: 1, name: 'La Palm Royal Beach Hotel', location: 'Accra' },
    { id: 2, name: 'Kempinski Hotel', location: 'Accra' },
    { id: 3, name: 'Royal Senchi Resort', location: 'Senchi' },
  ]);

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